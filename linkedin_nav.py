import os
from dotenv import load_dotenv
import random
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webdriver import WebDriver

def login_linkedin():
    load_dotenv()
    options = Options()
    # options.add_argument("user-data-dir=/Users/heba/Library/Application Support/Google/Chrome")
    # options.add_argument("user-data-dir=/Users/heba/Library/Application Support/Google/Chrome/Default")
    
    # options.add_argument("profile-directory=Profile 1")  # Use what you found in chrome://version
    options.add_argument("--remote-debugging-port=9222")  # Prevent new session issues
    driver = webdriver.Chrome(options=options)

    # Launch chrome and navigate to URL
    driver.get('https://www.linkedin.com/')

    # Check if we're already on the feed page
    if "https://www.linkedin.com/feed/" in driver.current_url:
        return driver

    # Look for "Sign in with email"
    # If found click it
    try:
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Sign in with email')]"))
        )
        login_button.click()
    except Exception as e:
        print("Login button not found or not clickable")

    email = os.getenv("EMAIL")
    passw = os.getenv("PASSW")
    
    # Find and input email and password
    # If 'Sign in' button found click it
    try:
        # locate email form by ID
        username = driver.find_element(By.ID, "username")
        username.send_keys(email)
        time.sleep(random.uniform(0.5, 3))  # Random delay
        # locate password form by ID 
        password = driver.find_element(By.ID, 'password')
        password.send_keys(passw)
        time.sleep(random.uniform(1, 3))  # Random delay
        # locate submit button by xpath
        sign_in_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Sign in')]")))
        # sign_in_button = driver.find_element(By.XPATH, '//*[@type="submit"]')
        sign_in_button.click()
    except Exception as e:
        print("Not on login page or elements not found")
    return driver

def go_to_connections(driver):
    """
    if on homepage:
    Homepage -> click Network -> click Connections
    Or
    Go to connections URL
    """
    if "https://www.linkedin.com/feed/" in driver.current_url:
        time.sleep(random.uniform(0.5, 3))  # Random delay
        network_button = driver.find_element(By.XPATH, "//a[contains(@href, 'mynetwork')]")
        network_button.click()
        # If im on the main network page
        current_url = driver.current_url
        if current_url.startswith("https://www.linkedin.com/mynetwork") and "/connections/" not in current_url:
            time.sleep(random.uniform(0.5, 3))  # Random delay
            # Capture the timestamp when the page is loaded
            timestamp = datetime.now()
            connections_button = driver.find_element(By.XPATH, "//a[contains(@href, 'connections')]")
            connections_button.click()
    else: 
        driver.get('https://www.linkedin.com/mynetwork/invite-connect/connections/')

# Cell 2: Open profile functions
def new_tab_link(driver, profile_link):
    """Open a profile in a new tab and switch to it"""
    profile_link.send_keys(Keys.COMMAND + Keys.RETURN)
    time.sleep(random.uniform(0.5, 1.5))
    driver.switch_to.window(driver.window_handles[-1])

def new_tab_url(driver, url):
    """Open a new tab using URL"""
    # Execute JavaScript to open a new tab with the URL
    driver.execute_script(f"window.open('{url}', '_blank');")
    time.sleep(random.uniform(0.5, 1.5))
    driver.switch_to.window(driver.window_handles[-1])

def close_tab(driver):
    """Close the current tab and return to the original tab"""
    driver.close()
    driver.switch_to.window(driver.window_handles[-1])
    time.sleep(random.uniform(1, 3))

def smooth_random_scroll(driver: WebDriver, steps=10, min_scroll=50, max_scroll=200, min_pause=0.5, max_pause=1.5):
    """
    Smoothly scrolls down the page in small, random increments to mimic human behavior.
    """
    for _ in range(steps):
        scroll_distance = random.randint(min_scroll, max_scroll)  # Random scroll amount
        driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
        time.sleep(random.uniform(min_pause, max_pause))  # Random delay

# Function to scroll using spacebar
def scroll_with_spacebar(driver, n=10):
    """
    Scroll down a page by sending spacebar keypresses
    """

    # Create action chain
    actions = ActionChains(driver)
    
    for y in range(n):
        for i in range(5):
            actions.send_keys(Keys.SPACE).perform()
            time.sleep(random.uniform(0.5, 1.5))
        time.sleep(random.uniform(2, 4))