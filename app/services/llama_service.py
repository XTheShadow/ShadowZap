import os
import xml.etree.ElementTree as ET # A library used to parse XML filews
from groq import Groq
from typing import List, Dict, Any, Optional # This library is used to define types for the functions
from dotenv import load_dotenv

# Loading environment the environment variable
load_dotenv()

# Initalizing the groq client
api_key = os.getenv('Llama_API_KEY')
client = Groq(api_key=api_key)

# A function to analyze the vulnerabilities in the XML report
def analyze_vulnerabilities(xml_report: str) -> Dict[str, Any]: # This means that the function takes the path to the xml report(string) as an argument and returns a dictionary containing the results of the analysis
    try:
        # Parsing the XML report
        tree = ET.parse(xml_report) # The xml report is parsed and stored in the tree variable
        root = tree.getroot() # The root of the XML tree is retrieved and stored in the root variable

        # Extracting the vulnerabilities from the report
        vulnerabilities = [] # A list for storing the vulnerabilities
        
        # Check if the report has any sites
        sites = root.findall(".//site")
        if not sites:
            print(f"Warning: No sites found in XML report: {xml_report}")
            # Returning an empty list of vulnerabilities
            vulnerabilities = []
        else:
            # Process the sites and their alerts for better handling
            for site in sites:
                # Try to find alerts - since they could be directly under site or in a nested alerts element
                alerts = site.findall(".//alertitem")
                if not alerts:
                    # Try another possible structure
                    alerts = site.findall("alerts/alertitem")
                
                if not alerts:
                    print(f"No alerts found for site {site.get('name', 'Unknown')}")
                    continue
                    
                for alert in alerts:
                    # Extracting alert details with proper validation
                    vulnerability = {
                       'name': get_element_text(alert, 'alert') or get_element_text(alert, 'name'),
                       'risk': get_element_text(alert, 'riskdesc'), # risckdesc is the risk level of the vulnerability
                       'description': get_element_text(alert, 'desc'), # desc is the description of the vulnerability
                       'solution': get_element_text(alert, 'solution'), # solution is the possible solution to the vulnerability 
                       'reference': get_element_text(alert, 'reference'), # A reference link for the vulnerability
                       'instances': []
                    }
                    
                    # Extracting the instances of the vulnerability
                    instances = alert.findall(".//instance")
                    if instances:
                        for instance in instances:
                            vulnerability['instances'].append({
                                'url': get_element_text(instance, 'uri'), # Adding the url of the instance to the list
                                'method': get_element_text(instance, 'method'), # Adding the method of the instance to the list
                                'evidence': get_element_text(instance, 'evidence'), # Adding the evidence to the list
                            })
                    
                    # Only adding vulnerabilities that have some content
                    if vulnerability['name'] or vulnerability['risk'] or vulnerability['description']:
                        vulnerabilities.append(vulnerability) # Adding the vulnerability to the vulnerabilities list
        
        # Logging the number of vulnerabilities found for better reporting
        print(f"Found {len(vulnerabilities)} vulnerabilities in {xml_report}")

        prompt = format_vulnerability_prompt(vulnerabilities, xml_report)
        # Sending the prompt to the llama model
        completion = client.chat.completions.create(
            model = "meta-llama/llama-4-maverick-17b-128e-instruct", # This is the model used
            messages=[
                {
                    "role": "user",
                    "content": prompt # Here I pass the prompt to the model
                }
            ]
        )

        # To Extract the response
        response = completion.choices[0].message.content 
        
        # Getting the base name of the xml report without the extension
        base_name = os.path.splitext(os.path.basename(xml_report))[0] 
        response_file_name = base_name + ".md"
        
        # Ensuring that the output directory exists
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports", "outputs")
        os.makedirs(output_dir, exist_ok=True)
        
        # Saving the response to a file
        response_output_path = os.path.join(output_dir, response_file_name)
        with open(response_output_path, "w") as f:
            f.write(response)

        return {
            "success": True,
            "response": response,
            "vulnerabilities": vulnerabilities
        }
        
    except Exception as e:
        print(f"Error analyzing vulnerabilities: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


# I made this function to format the vunerability data into a prompt for the llma model and also to have the prompt that Im going to use
def format_vulnerability_prompt(vulnerabilities: list, xml_report: str) -> str:

    prompt = '''You are a cybersecurity-savvy technical writer. Your task is to reformat and enhance a vulnerability scanning report generated by OWASP ZAP. The report includes a list of alerts categorized by severity and detailed information about each alert.

**Objectives:**
1. Translate technical descriptions into clear, understandable language for a broader audience (e.g., developers, managers).
2. Preserve all essential technical details (risk level, URLs, attack vectors, evidence, and solutions).
3. Organize the output into an elegant, readable format (markdown or HTML), with sections for:
   - Executive Summary
   - Vulnerability Overview by Severity
   - Detailed Findings
   - Recommended Actions
   - Glossary
4. Style and format it in a modern, minimal report design, similar to a consulting security assessment (white-label report).
5. Make sure to mantain the same urls as in the original report.

**Context for this Project:**
This report is part of an automated penetration testing tool that integrates OWASP ZAP with AI to generate more digestible security reports. The goal is to help non-experts understand vulnerabilities and fix them.

**IMPORTANT INSTRUCTIONS:**
1. If no vulnerabilities are provided or the data is empty, create a "clean" report indicating that no vulnerabilities were detected, but still include sections for methodology and recommended security practices.
2. For each vulnerability, make sure to include a clear description, the affected URLs, and actionable remediation steps.
3. If vulnerability data appears incomplete (empty fields), still create a structured report with the available information and note what's missing.
4. Always create a proper Executive Summary that provides an overview of the scan, even if no issues were detected.

Here is the extracted vulnerability data from the ZAP scan:
'''

    # Adding the vulnerability data to the prompt
    prompt += "\n### Vulnerability Data \n"

    # Checking if there are any non-empty vulnerabilities to avoid generating an empty report
    has_data = False
    for vuln in vulnerabilities:
        if vuln.get('name') or vuln.get('risk') or vuln.get('description'):
            has_data = True
            break

    if not has_data:
        prompt += "\nNo significant vulnerabilities were detected in this scan. Please generate a clean report indicating this, but still include best practices and security recommendations.\n"
    else:
        # Limit to a reasonable number of vulnerabilities to avoid token limit issues
        max_vulnerabilities = 10
        if len(vulnerabilities) > max_vulnerabilities:
            prompt += f"\nFound {len(vulnerabilities)} vulnerabilities. Here are the {max_vulnerabilities} most important ones:\n"
            # Sort vulnerabilities by risk level if available
            vulnerabilities_to_process = sorted(
                vulnerabilities,
                # This line sorts the vulnerabilities by their risk level, with "High" being the highest and "Low" being the lowest. 
                key=lambda v: 0 if not v.get('risk') else (3 if 'High' in v.get('risk', '') else (2 if 'Medium' in v.get('risk', '') else 1)),
                reverse=True
            )[:max_vulnerabilities] # This line limits the number of vulnerabilities to the first 10 to avoid token limit issues(LLaMA related)
        else:
            vulnerabilities_to_process = vulnerabilities
            
        # Iterating over the vulnerabilities, "enumerate" is a function that returns a tuple containing a count (starting from 0 by default) and the values obtained from iterating over the sequence
        # "enumerate(vulnerabilities_to_process, 1)" means that the count will start from 1 instead of 0
        for i, vulnerability in enumerate(vulnerabilities_to_process, 1):
            prompt += f"\nVulnerability {i}: {vulnerability.get('name', 'Unknown')}\n"
            prompt += f"- Risk Level: {vulnerability.get('risk', 'Unknown')}\n"
            
            # Truncating very long descriptions to avoid token limit issues
            description = vulnerability.get('description', 'Unknown')
            if len(description) > 500:
                description = description[:497] + "..."
            prompt += f"- Description: {description}\n"
            
            # Truncating very long solutions to avoid token limit issues
            solution = vulnerability.get('solution', 'Unknown')
            if len(solution) > 500:
                solution = solution[:497] + "..."
            prompt += f"- Solution: {solution}\n"

            # Adding the instances to the prompt - limit to 3 examples per vulnerability
            instances = vulnerability.get('instances', []) # Getting the instances of the vulnerability , an empty list is returned if the instances are not found
            
            if instances:
                prompt += "\n -Instances:\n"
                # Limit the number of instances to avoid token limit issues
                max_instances = min(3, len(instances))
                # Iterating over the instances to add them to the prompt
                for j, instance in enumerate(instances[:max_instances], 1): # :max_instances 1 is the starting index for the enumeration
                    prompt += f"  Instance {j}:\n"
                    prompt += f"  - URL: {instance.get('url', 'Unknown')}\n"
                    prompt += f"  - Method: {instance.get('method', 'Unknown')}\n"
                    
                    evidence = instance.get('evidence', 'Unknown')
                    if len(evidence) > 100:
                        evidence = evidence[:97] + "..."
                    prompt += f"  - Evidence: {evidence}\n"
                
                if len(instances) > max_instances:
                    prompt += f"  (+ {len(instances) - max_instances} more instances not shown for brevity)\n"
            
            # Adding a separator between the vulnerabilities
            if i < len(vulnerabilities_to_process):
                prompt += "\n---\n"
        
        if len(vulnerabilities) > max_vulnerabilities:
            prompt += f"\n\nNote: Only showing {max_vulnerabilities} out of {len(vulnerabilities)} total vulnerabilities. The report should indicate this limitation and focus on the most critical issues."

    prompt += "\n\nPlease return the output as markdown suitable for use on a webpage or as a downloadable PDF. Format your response as clean markdown without any additional commentary. Even if there are no vulnerabilities, create a complete and professional-looking report with appropriate sections."

    return prompt

# Helper function to safely extract the text from the XML elements
def get_element_text(element, tag_name: str) -> str:
    child = element.find(tag_name)
    if child is not None and child.text:
        return child.text
    else:
        return ""