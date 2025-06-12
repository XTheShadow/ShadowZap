import os
import re # The re module is used for regular expressions
import markdown
from weasyprint import HTML 
from html import escape # The escape function is used to escape special characters in HTML
from string import Template # For template substitution
from datetime import datetime
import base64  # For encoding images as base64

# The main function that enhances the report(In terms of visuals)
def enhance_report(input_md_path=None, output_dir=None, preserve_filename=True, output_format="both", target_url=None, scan_type=None):
   
    # Handling the default paths
    if input_md_path is None:
        input_md_path = "reports/outputs/zap_report_20250528_161544.md"
    
    if output_dir is None:
        output_dir = "reports/final"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine output filenames based on input
    if preserve_filename:
        # Extracting the base name without the extension
        base_name = os.path.splitext(os.path.basename(input_md_path))[0]
        # If it ends with _response, remove it to maintain consistency
        if base_name.endswith("_response"):
            base_name = base_name[:-9]
    else:
        base_name = "zap_report"
    
    # Define output paths
    output_html_path = os.path.join(output_dir, f"{base_name}.html")  # HTML for PDF generation
    output_pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
    web_output_path = os.path.join(output_dir, f"{base_name}_web.html")
    
    # === Load Markdown Content ===
    with open(input_md_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    
    # === Parse Severity Counts and Extract Key Information from Markdown ===
    high_count = len(re.findall(r'(?i)(\*\*)?Risk Level:(\*\*)?\s*High', markdown_text))
    medium_count = len(re.findall(r'(?i)(\*\*)?Risk Level:(\*\*)?\s*Medium', markdown_text))
    low_count = len(re.findall(r'(?i)(\*\*)?Risk Level:(\*\*)?\s*Low', markdown_text))
    
    # === Extract Sections from Markdown ===
    
    # Extract Executive Summary
    exec_summary = ""
    exec_summary_match = re.search(r'(?:^|\n)# Executive Summary\s+([\s\S]*?)(?=\n##|\n#|$)', markdown_text)
    if not exec_summary_match:
        # Try alternate pattern
        exec_summary_match = re.search(r'(?:^|\n)## Executive Summary\s+([\s\S]*?)(?=\n##|\n#|$)', markdown_text)
    
    if exec_summary_match and exec_summary_match.group(1):
        exec_summary = exec_summary_match.group(1).strip()
    
    # Convert markdown to HTML for exec_summary
    exec_summary = markdown.markdown(exec_summary)
    
    # === Use provided target URL or extract from markdown ===
    if not target_url:
        target_url = "Unknown Target"
        # Try to extract from markdown
        print("No target URL provided, attempting to extract from markdown...")
    
    

    # === Use provided scan type or extract from markdown ===
    if not scan_type:
        scan_type = "Unknown Scan Type"
        # Try to extract from markdown
        print("No scan type provided, attempting to extract from markdown...")
        
        
    
    # Extract Recommendations if present
    recommendations_section = None
    recommendations_match = re.search(r'(?:^|\n)## Recommended Actions|## Recommendations\s+([\s\S]*?)(?=\n##|\n#|$)', markdown_text)
    if recommendations_match and recommendations_match.group(1):
        recommendations_section = recommendations_match.group(1).strip()
    
    # Extract Glossary if present
    glossary_section = None
    glossary_match = re.search(r'(?:^|\n)## Glossary\s+([\s\S]*?)(?=\n##|\n#|$)', markdown_text)
    if glossary_match and glossary_match.group(1):
        glossary_section = glossary_match.group(1).strip()
    
    # Extract Detailed Findings section
    detailed_findings_section = ""
    detailed_findings_match = re.search(r'(?:^|\n)## Detailed Findings\s+([\s\S]*?)(?=\n## Recommended Actions|\n## Recommendations|\n## Glossary|\n#|$)', markdown_text)
    if detailed_findings_match and detailed_findings_match.group(1):
        detailed_findings_section = detailed_findings_match.group(1).strip()
        
    # Extract Vulnerability Overview section if present
    vulnerability_overview_section = ""
    vuln_overview_match = re.search(r'(?:^|\n)## Vulnerability Overview\s+([\s\S]*?)(?=\n## Detailed Findings|\n## Recommended Actions|\n## Recommendations|\n## Glossary|\n#|$)', markdown_text)
    if vuln_overview_match and vuln_overview_match.group(1):
        vulnerability_overview_section = vuln_overview_match.group(1).strip()
    
    # === Extract Detailed Findings ===
    detailed_findings = []
    
    # Direct approach to extract vulnerability information from markdown
    # Pattern to match numbered headings like "### 1. Content Security Policy"
    numbered_heading_pattern = re.compile(r'(?:^|\n)### (\d+)\.\s*(.*?)(?=\n)')
    
    # Store all findings
    all_findings = []
    
    for match in numbered_heading_pattern.finditer(markdown_text):
        number = match.group(1)
        title = match.group(2).strip()
        
        # Find the content between this heading and the next heading
        start_pos = match.end()
        next_heading = re.search(r'(?:\n###|\n##|\n#)', markdown_text[start_pos:])
        end_pos = start_pos + next_heading.start() if next_heading else len(markdown_text)
        content = markdown_text[start_pos:end_pos].strip()
        
        # Extract basic information
        risk = "Low"  # Default
        risk_match = re.search(r'\*\s*Risk Level:\s*(\w+)', content, re.IGNORECASE)
        if risk_match:
            risk = risk_match.group(1)
            
        description = ""
        desc_match = re.search(r'\*\s*Description:\s*(.*?)(?=\n\*|\Z)', content, re.DOTALL | re.IGNORECASE)
        if desc_match:
            description = desc_match.group(1).strip()
            
        # Try to extract URLs
        urls = ""
        urls_match = re.search(r'\*\s*(?:Affected )?URLs?:\s*(.*?)(?=\n\*|\Z)', content, re.DOTALL | re.IGNORECASE)
        # If no match with the standard pattern, try alternative patterns
        if not urls_match:
            # Try to find any URLs in the content
            url_pattern = re.compile(r'https?://[^\s\'"<>]+')
            all_urls = url_pattern.findall(content)
            if all_urls:
                urls = "\n".join([f"+ {url}" for url in all_urls])
        
        if urls_match:
            urls = urls_match.group(1).strip()
            
        # Try to extract solution
        solution = ""
        solution_match = re.search(r'\*\s*Solution:\s*(.*?)(?=\n\*|\Z)', content, re.DOTALL | re.IGNORECASE)
        if solution_match:
            solution = solution_match.group(1).strip()
            
        finding = {
            'title': title,
            'risk': risk,
            'description': description,
            'urls': urls,
            'evidence': "",
            'solution': solution,
            'attack_vector': ""
        }
        
        all_findings.append(finding)
    
    # Sort by number to maintain order
    detailed_findings = all_findings
    
    print(f"Extracted {len(detailed_findings)} findings")
    
    # === Generate HTML content for findings ===
    def generate_findings_html(detailed_findings, for_pdf=True):
        findings_html = ""
        
        if for_pdf:
            # PDF-optimized findings layout with page breaks
            if not detailed_findings:
                findings_html = ""  # Don't show any message when no vulnerabilities found
            else:
                # Group findings in sets of 3 for better pagination
                for i in range(0, len(detailed_findings), 3):
                    # Start a findings group (for better pagination)
                    if i + 3 >= len(detailed_findings):
                        findings_html += '<div class="findings-group last-group">\n'
                    else:
                        findings_html += '<div class="findings-group">\n'
                    
                    # Add up to 3 findings in this group
                    group_end = min(i + 3, len(detailed_findings))
                    for j in range(i, group_end):
                        finding = detailed_findings[j]
                        risk_class = "high-risk" if finding['risk'].lower() == 'high' else "medium-risk" if finding['risk'].lower() == 'medium' else "low-risk"
                        if finding['risk'].lower() == 'informational':
                            risk_class = "informational-risk"
                        
                        findings_html += f'''
                        <div class="finding-card {risk_class}">
                          <h3>{escape(finding['title'])}</h3>
                          <p><strong>Risk Level:</strong> <span class="badge badge-{finding['risk'].lower()}">{finding['risk']}</span></p>
                          
                          <div class="description">
                            <p><strong>Description:</strong> <span style="font-size:0.85rem;">{escape(finding['description'])}</span></p>
                          </div>
                        '''
                        
                        if finding['urls']:
                            # Format URLs as a stacked list
                            formatted_urls = escape(finding['urls'])
                            # Replace "+ http" patterns with line breaks and bullets
                            formatted_urls = re.sub(r'(?:\+|\*)\s+(https?://[^\s]+)', r'• \1<br>', formatted_urls)
                            # Also handle any remaining URLs that might be line-separated
                            formatted_urls = re.sub(r'\n\s*(?:\+|\*)\s+(https?://[^\s]+)', r'<br>• \1', formatted_urls)
                            
                            findings_html += f'''
                            <div>
                              <p><strong>URLs:</strong> <span style="color: #00ff88; font-size: 0.8rem;">(Affected URLs)</span></p>
                              <div class="url-list">{formatted_urls}</div>
                            </div>
                            '''
                        
                        if finding['attack_vector']:
                            findings_html += f'''
                            <p><strong>Attack Vector:</strong> <span style="font-size:0.85rem;">{escape(finding["attack_vector"])}</span></p>
                            '''
                        
                        if finding['evidence']:
                            findings_html += f'''
                            <div>
                              <p><strong>Evidence:</strong></p>
                              <div class="evidence-block">{escape(finding["evidence"])}</div>
                            </div>
                            '''
                        
                        if finding['solution']:
                            # Format solution similar to other sections (no special box)
                            findings_html += f'''
                            <div>
                              <p><strong>Solution:</strong> <span style="font-size:0.85rem;">{escape(finding["solution"])}</span></p>
                            </div>
                            '''
                        
                        findings_html += '</div>\n'
                    
                    # End the findings group
                    findings_html += '</div>\n'
        else:
            # Web-optimized findings layout (no page breaks, continuous flow)
            if not detailed_findings:
                findings_html = ""  # Don't show any message when no vulnerabilities found
            else:
                for finding in detailed_findings:
                    risk_class = "high-risk" if finding['risk'].lower() == 'high' else "medium-risk" if finding['risk'].lower() == 'medium' else "low-risk"
                    
                    findings_html += f'''
                    <div class="finding-card {risk_class}">
                      <h3>{escape(finding['title'])}</h3>
                      <p><strong>Risk Level:</strong> <span class="badge badge-{finding['risk'].lower()}">{finding['risk']}</span></p>
                      
                      <div class="description">
                        <p><strong>Description:</strong> <span style="font-size:0.85rem;">{escape(finding['description'])}</span></p>
                      </div>
                    '''
                    
                    if finding['urls']:
                        # Format URLs as a stacked list
                        formatted_urls = escape(finding['urls'])
                        # Replace "+ http" patterns with line breaks and bullets
                        formatted_urls = re.sub(r'(?:\+|\*)\s+(https?://[^\s]+)', r'• \1<br>', formatted_urls)
                        # Also handle any remaining URLs that might be line-separated
                        formatted_urls = re.sub(r'\n\s*(?:\+|\*)\s+(https?://[^\s]+)', r'<br>• \1', formatted_urls)
                        
                        findings_html += f'''
                        <div>
                          <p><strong>URLs:</strong> <span style="color: #00ff88; font-size: 0.8rem;">(Affected URLs)</span></p>
                          <div class="url-list">{formatted_urls}</div>
                        </div>
                        '''
                    
                    if finding['attack_vector']:
                        findings_html += f'''
                        <p><strong>Attack Vector:</strong> <span style="font-size:0.85rem;">{escape(finding["attack_vector"])}</span></p>
                        '''
                    
                    if finding['evidence']:
                        findings_html += f'''
                        <div>
                          <p><strong>Evidence:</strong></p>
                          <div class="evidence-block">{escape(finding["evidence"])}</div>
                        </div>
                        '''
                    
                    if finding['solution']:
                        # Format solution similar to other sections (no special box)
                        findings_html += f'''
                        <div>
                          <p><strong>Solution:</strong> <span style="font-size:0.85rem;">{escape(finding["solution"])}</span></p>
                        </div>
                        '''
                    
                    findings_html += '</div>\n'
                
        return findings_html
    
    # === Load template files ===
    def load_template(template_name):
        template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                    'reports', 'templates', template_name)
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
            
            # Find all script sections
            script_pattern = re.compile(r'<script>(.*?)</script>', re.DOTALL)
            scripts = script_pattern.findall(template_content)
            
            # Replace each script block with an escaped version
            for script in scripts:
                # Escape all $ in script sections
                escaped_script = script.replace('$', '$$')
                template_content = template_content.replace(script, escaped_script)
            
            # Now fix the template variables we need to preserve
            template_vars = {
                '${high_count}': '${high_count}',
                '${medium_count}': '${medium_count}',
                '${low_count}': '${low_count}',
                '${info_count}': '${info_count}',
                '${executive_summary}': '${executive_summary}',
                '${high_findings}': '${high_findings}',
                '${medium_findings}': '${medium_findings}',
                '${low_findings}': '${low_findings}',
                '${info_findings}': '${info_findings}',
                '${pdf_findings_html}': '${pdf_findings_html}',
                '${recommendations}': '${recommendations}',
                '${target_url}': '${target_url}',
                '${scan_type}': '${scan_type}',
                '${report_date}': '${report_date}',
                '${glossary}': '${glossary}',
                '${hacker_icon_base64}': '${hacker_icon_base64}'
            }
            
            for placeholder, replacement in template_vars.items():
                # Replace the double-escaped version with the single-escaped version
                double_escaped = placeholder.replace('$', '$$')
                template_content = template_content.replace(double_escaped, placeholder)
                
            return Template(template_content)
    
    # === Get base64 encoded icon ===
    def get_base64_icon():
        icon_path = os.path.join(os.path.dirname(__file__), 'hacker-icon.png')
        if os.path.exists(icon_path):
            with open(icon_path, 'rb') as icon_file:
                encoded_icon = base64.b64encode(icon_file.read()).decode('utf-8')
                return f"data:image/png;base64,{encoded_icon}"
        return ""  # Return empty string if icon not found
    
    # === Generate HTML for PDF and Web ===
    # For PDF output
    if output_format in ["pdf", "both"]:
        # Generate PDF-optimized findings HTML
        # Instead of separate sections, combine all findings and sort by risk level
        all_findings = sorted(detailed_findings, key=lambda f: 
                             0 if f['risk'] == 'High' else 
                             1 if f['risk'] == 'Medium' else 
                             2 if f['risk'] == 'Low' else 3)
        
        # Group findings in sets of 3 for better pagination
        pdf_findings_html = ""
        for i in range(0, len(all_findings), 3):
            # Start a findings group (for better pagination)
            if i + 3 >= len(all_findings):
                pdf_findings_html += '<div class="findings-group last-group">\n'
            else:
                pdf_findings_html += '<div class="findings-group">\n'
            
            # Add up to 3 findings in this group
            group_end = min(i + 3, len(all_findings))
            for j in range(i, group_end):
                finding = all_findings[j]
                risk_class = "high-risk" if finding['risk'].lower() == 'high' else "medium-risk" if finding['risk'].lower() == 'medium' else "low-risk"
                if finding['risk'].lower() == 'informational':
                    risk_class = "informational-risk"
                
                # Removed risk level headings for cleaner PDF layout
                
                pdf_findings_html += f'''
                <div class="finding-card {risk_class}">
                  <h3>{escape(finding['title'])}</h3>
                  <p><strong>Risk Level:</strong> <span class="badge badge-{finding['risk'].lower()}">{finding['risk']}</span></p>
                  
                  <div class="description">
                    <p><strong>Description:</strong> <span style="font-size:0.85rem;">{escape(finding['description'])}</span></p>
                  </div>
                '''
                
                if finding['urls']:
                    # Format URLs as a stacked list
                    formatted_urls = escape(finding['urls'])
                    # Replace "+ http" patterns with line breaks and bullets
                    formatted_urls = re.sub(r'(?:\+|\*)\s+(https?://[^\s]+)', r'• \1<br>', formatted_urls)
                    # Also handle any remaining URLs that might be line-separated
                    formatted_urls = re.sub(r'\n\s*(?:\+|\*)\s+(https?://[^\s]+)', r'<br>• \1', formatted_urls)
                    
                    pdf_findings_html += f'''
                    <div>
                      <p><strong>URLs:</strong> <span style="color: #00ff88; font-size: 0.8rem;">(Affected URLs)</span></p>
                      <div class="url-list">{formatted_urls}</div>
                    </div>
                    '''
                
                if finding['attack_vector']:
                    pdf_findings_html += f'''
                    <p><strong>Attack Vector:</strong> <span style="font-size:0.85rem;">{escape(finding["attack_vector"])}</span></p>
                    '''
                
                if finding['evidence']:
                    pdf_findings_html += f'''
                    <div>
                      <p><strong>Evidence:</strong></p>
                      <div class="evidence-block">{escape(finding["evidence"])}</div>
                    </div>
                    '''
                
                if finding['solution']:
                    # Format solution similar to other sections (no special box)
                    pdf_findings_html += f'''
                    <div>
                      <p><strong>Solution:</strong> <span style="font-size:0.85rem;">{escape(finding["solution"])}</span></p>
                    </div>
                    '''
                
                pdf_findings_html += '</div>\n'
            
            # End the findings group
            pdf_findings_html += '</div>\n'
        
        # Keep empty sections for template compatibility
        pdf_high_findings = ""
        pdf_medium_findings = ""
        pdf_low_findings = ""
        pdf_info_findings = ""
        
        # Convert recommendations section to HTML if it exists
        recommendations_html = ""
        if recommendations_section:
            recommendations_html = markdown.markdown(recommendations_section)
        
        # Convert vulnerability overview section to HTML if it exists
        vulnerability_overview_html = ""
        if vulnerability_overview_section:
            vulnerability_overview_html = markdown.markdown(vulnerability_overview_section)
        
        # Convert glossary section to HTML if it exists
        glossary_html = ""
        if glossary_section:
            glossary_html = markdown.markdown(glossary_section)
        
        # Load PDF template
        pdf_template = load_template('pdf_template.html')
        
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Count info findings
        info_count = len([f for f in detailed_findings if f['risk'] == 'Informational'])
        
        # Substitute values
        pdf_html = pdf_template.substitute(
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            info_count=info_count,
            executive_summary=exec_summary,
            high_findings=pdf_high_findings,
            medium_findings=pdf_medium_findings,
            low_findings=pdf_low_findings,
            info_findings=pdf_info_findings,
            pdf_findings_html=pdf_findings_html,
            recommendations=recommendations_html,
            target_url=target_url,
            scan_type=scan_type,
            report_date=current_date,
            glossary=glossary_html,
            hacker_icon_base64=get_base64_icon()
        )
        
        # Write PDF-optimized HTML File
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(pdf_html)
        
        # Convert HTML to PDF
        try:
            print(f"Generating PDF report at {output_pdf_path}")
            HTML(string=pdf_html).write_pdf(output_pdf_path)
            print(f"PDF generation complete")
        except Exception as e:
            print(f"Error during PDF generation: {e}")
            print("Falling back to HTML-only output")
            # PDF file won't be created, but HTML is still available
    
    # For Web output
    if output_format in ["web", "both"]:
        # Generate web-optimized findings HTML
        web_high_findings = generate_findings_html([f for f in detailed_findings if f['risk'] == 'High'], for_pdf=False)
        web_medium_findings = generate_findings_html([f for f in detailed_findings if f['risk'] == 'Medium'], for_pdf=False)
        web_low_findings = generate_findings_html([f for f in detailed_findings if f['risk'] == 'Low'], for_pdf=False)
        web_info_findings = generate_findings_html([f for f in detailed_findings if f['risk'] == 'Informational'], for_pdf=False)
        
        # Convert recommendations section to HTML if it exists
        recommendations_html = ""
        if recommendations_section:
            recommendations_html = markdown.markdown(recommendations_section)
        
        # Convert vulnerability overview section to HTML if it exists
        vulnerability_overview_html = ""
        if vulnerability_overview_section:
            vulnerability_overview_html = markdown.markdown(vulnerability_overview_section)
        
        # Convert glossary section to HTML if it exists
        glossary_html = ""
        if glossary_section:
            glossary_html = markdown.markdown(glossary_section)
        
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Count info findings
        info_count = len([f for f in detailed_findings if f['risk'] == 'Informational'])
        
        # Load web template
        web_template = load_template('enhanced_template.html')
        
        # Substitute values
        web_html = web_template.substitute(
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            info_count=info_count,
            executive_summary=exec_summary,
            high_findings=web_high_findings,
            medium_findings=web_medium_findings,
            low_findings=web_low_findings,
            info_findings=web_info_findings,
            pdf_findings_html="",
            recommendations=recommendations_html,
            target_url=target_url,
            scan_type=scan_type,
            report_date=current_date,
            glossary=glossary_html,
            hacker_icon_base64=get_base64_icon()
        )
        
        # Write web-optimized HTML file
        with open(web_output_path, "w", encoding="utf-8") as f:
            f.write(web_html)
        print(f"Web-optimized HTML report generated at {web_output_path}")
    
    # === Return paths ===
    result = {
        "html_path": output_html_path,
        "pdf_path": output_pdf_path,
        "severity_counts": {
            "high": high_count,
            "medium": medium_count,
            "low": low_count
        }
    }
    
    # Add web path if web output was generated
    if output_format in ["web", "both"]:
        result["web_html_path"] = web_output_path
    
    print(f"✔ Report enhanced!")
    print(f"   PDF : {result['pdf_path']}")
    if output_format in ["web", "both"]:
        print(f"   Web : {result['web_html_path']}")
    return result

# For backward compatibility and direct script execution
if __name__ == "__main__":
    enhance_report()