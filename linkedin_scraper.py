import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import timedelta, datetime
from selenium.webdriver.common.by import By

def extract_connections(driver):
    """Extract people info from connections page"""
    timestamp = datetime.now()
    current_url = driver.current_url
    if current_url.startswith("https://www.linkedin.com/mynetwork") and "/connections/" in current_url:
        connections = driver.find_elements(By.CLASS_NAME, "mn-connection-card")
        connections_data = []
        for connection in connections:
            try:
                name = connection.find_element(By.CLASS_NAME, "mn-connection-card__name").text.strip()
                profile_url = connection.find_element(By.CLASS_NAME, "mn-connection-card__picture").get_attribute("href")
                occupation = connection.find_element(By.CLASS_NAME, "mn-connection-card__occupation").text.strip()
                time_badge = connection.find_element(By.CLASS_NAME, "time-badge").text.strip()
                connected_at = (timestamp - extract_timedelta(time_badge)).strftime("%Y-%m-%d") 
                connections_data.append([name, occupation, profile_url, connected_at])
            except Exception as e:
                print(f"Skipping due to error: {e}")
        df = pd.DataFrame(connections_data, columns=["Name", "Header", "URL", "Connected At"])
        return df

# Cell 3: Extract About section
def extract_about(driver):
    """Extract the About section from a profile"""
    try:
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        section_soup = soup.find_all(string="About")[0]
        section_section = section_soup.parent.find_parent("section")
        section_elements = section_section.find_all('span')
        section_text = []
        
        for span in section_elements:
            if span.get("aria-hidden") != "true" and span.get_text(strip=True) not in ["About", "…see more"]:
                section_text.append(span.get_text(strip=True))
        
        about = " ".join(section_text) if section_text else "Empty about section"
            
        return {"About": about}
    except Exception as e:
        return {"About": "Not found"}

# Cell 5: Extract all experiences
def extract_experiences(driver, first_only = False):
    """Extract all experiences from a profile"""
    all_experiences = []
    try:
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        section_soup = soup.find_all(string="Experience")[0]
        section_parent = section_soup.parent.find_parent("section")
        companies_list = section_parent.find("ul")
        company_blocks = companies_list.find_all("li", recursive=False)
        for i, company in enumerate(company_blocks):
            experience = {
                "URL": driver.current_url,
                "Company": "Not found",
                "Title": "Not found",
                "Duration": "Not found"
            }
            exp_parts = company.select("span")
            exp_parts = [exp.get_text(strip=True) for exp in exp_parts if exp.get("aria-hidden") != "true"]
            exp_parts = [exp for exp in exp_parts if exp.strip()] # remove empty strings
            exp_copy = exp_parts.copy() # remove repeated strings
            for exp1 in exp_parts:
                for exp2 in exp_parts:
                    exp11 = re.sub(r'[^a-zA-Z0-9]', '', 2*exp1.lower().replace("to","")).strip()
                    exp22 = re.sub(r'[^a-zA-Z0-9]', '', exp2.lower().replace("to","")).strip()
                    if exp11 == exp22 and exp1 != exp2:
                        exp_copy.remove(exp2)
            duration = None
            for exp in exp_copy:
                if is_duration(exp):
                    duration = exp
                    break  # Stop at first valid duration
            exp_copy.remove(duration)
            exp_parts = exp_copy
            if company.find("ul") is not None:
                title = exp_parts[1]
                company = exp_parts[0].split("·")[0].strip()
            else:
                title = exp_parts[0]
                company = exp_parts[1].split("·")[0].strip()
            
            # Find duration in span elements
            experience["Company"] = company if company else "Not found"
            experience["Title"] = title if title else "Not found"
            experience["Duration"] = duration if duration else "Not found"
        
            all_experiences.append(experience)

        return all_experiences[0] if first_only else all_experiences
            
    except Exception as e:
        return []

# Cell 6: Main scraping function for a single profile
def scrape_profile(driver):
    """Scrape data from the currently open profile"""
    profile_url = driver.current_url
    profile_info = {"URL": profile_url}
    
    # Extract sections
    about_info = extract_about(driver)
    experience_info = extract_experiences(driver, first_only=True)
    
    # Update profile info
    profile_info.update(about_info)
    profile_info.update(experience_info)
    
    # Get all experiences
    # all_experiences = extract_experiences(driver)
    
    return profile_info

def get_profile_links(driver):
    """
    Extracts LinkedIn profile links & URLs from the connections page.
    """
    profile_links = driver.find_elements(By.CSS_SELECTOR, ".mn-connection-card__link")
    profile_urls = [link.get_attribute("href") for link in profile_links if link.get_attribute("href")]
    return profile_links, profile_urls

def is_duration(text):
    """
    Checks if the given text follows a duration format.
    
    A valid duration must contain both numbers and letters, 
    and can include "-", "·" as separators.
    """
    parts = text.split()
    has_numbers = any(part.isdigit() for part in parts)
    has_letters = any(part.isalpha() for part in parts)
    valid = all(part.isalpha() or part.isdigit() or part in ["-", "·"] for part in parts)

    return valid and has_numbers and has_letters

def extract_timedelta(connected_text):
    """
    Extracts the time value from 'Connected X hours/days ago'
    and converts it into an actual timestamp.
    """
    match = re.search(r"Connected (\d+) (\w+) ago", connected_text)
    
    if match:
        num = int(match.group(1))  # Extract the number (e.g., 3)
        unit = match.group(2)  # Extract the time unit (e.g., "hours", "days")

        # Convert the extracted time into a datetime
        if "minute" in unit:
            return timedelta(minutes=num)
        elif "hour" in unit:
            return timedelta(hours=num)
        elif "day" in unit:
            return timedelta(days=num)
        elif "week" in unit:
            return timedelta(weeks=num)
        elif "month" in unit:
            return timedelta(days=num * 30)  # Approximate months as 30 days
        elif "year" in unit:
            return timedelta(days=num * 365)  # Approximate years as 365 days

    return None  # Return None if format is unrecognized