import os
import xml.etree.ElementTree as ET # A library used to parse XML filews
from groq import Groq
from typing import List, Dict, Any # This library is used to define types for the functions

# Initalizing the groq client
client = Groq()

# A function to analyze the vulnerabilities in the XML report
def analyze_vulnerabilities(xml_report: str) -> Dict[str, Any]: # This means that the function takes the path to the xml report(string) as an argument and returns a dictionary containing the results of the analysis
    try:
        # Parsing the XML report
        tree = ET.parse(xml_report) # The xml report is parsed and stored in the tree variable
        root = tree.getroot() # The root of the XML tree is retrieved and stored in the root variable

        # Extracting the vulnerabilities from the report
        vulnerabilities = [] # A list for storing the vulnerabilities
        for site in root.findall(".//site"): # Iterating over all the sites in the XML report
            for alert in site.findall(".//alert"): # Iterating over all the alerts in the XML report
                vulnerability = {
                   'name': get_element_text(alert, 'name'),
                   'risk': get_element_text(alert, 'riskdesc'), # risckdesc is the risk level of the vulnerability
                   'descritption': get_element_text(alert, 'desc'), # desc is the description of the vulnerability
                   'solution': get_element_text(alert, 'solution'), # solution is the possible solution to the vulnerability 
                   'reference': get_element_text(alert, 'reference'), # A reference link for the vulnerability
                   'instances': []
                }
                # Extracting the instances of the vulnerabailty
                for instance in alert.findall(".//instance"): # Iterating over all the instances of the vulnerability
                    vulnerabaility['instances'].append({
                        'url': get_element_text(instance, 'uri'), # Adding the url of the instance to the list
                        'method': get_element_text(instance, 'method'), # Adding the method of the instance to the list
                        'evidence': get_element_text(instance,'evidence'), # Adding the evidence to the list
                    })
                vulnerabilities.append(vulnerability) # Adding the vulnerability to the vulnerabailites list
        

        ''' The Llma model will be integrated here to analyze the vulnerabilities'''
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
                    
