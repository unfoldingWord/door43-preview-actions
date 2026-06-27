from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time


completed_urls = []
try:
  with open('./completed_urls', 'r') as file:
    completed_urls = file.read().splitlines()
except FileNotFoundError:
  pass

# Setup Chrome options
chrome_options = webdriver.ChromeOptions()

# Set the location of the webdriver
webdriver_service = Service(ChromeDriverManager().install())

# Initialize the driver
driver = webdriver.Chrome(service=webdriver_service, options=chrome_options)

root = 'https://preview.door43.org'
# Open the webpage
#driver.get(root + "?owner=unfoldingWord&owner=Door43-Catalog&subject=Aligned+Bible&subject=Bible&subject=Greek+New+Testament&subject=Hebrew+Old+Testament&subject=Open+Bible+Stories&subject=Translation+Words&subject=TSV+Translation+Notes&subject=TSV+Translation+Questions&stage=latest&sort=released&order=desc")
driver.get(root + "?subject=Aligned+Bible&subject=Bible&subject=Open+Bible+Stories&subject=Translation+Words&subject=TSV+Translation+Notes&subject=TSV+Translation+Questions&stage=latest&sort=released&order=desc")
#driver.get(root + "?owner=unfoldingWord&owner=Door43-Catalog&subject=TSV%20Translation%20Notes&stage=latest&sort=released&order=desc")

# Wait for the component to load
wait = WebDriverWait(driver, 60)  # adjust the timeout as needed
# wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'css-c0czuf')))  # replace with the actual class name of your component
time.sleep(10)

# time.sleep(3)

# # Click the button with class name "css-1ujsas3"
# button = driver.find_element(By.CLASS_NAME, 'css-1ujsas3')
# button.click()
# # Wait for a few seconds before clicking the button
# time.sleep(3)

# Wait for the button with class name "css-1ujsas3" to appear again
# wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'css-1ujsas3')))

# print(driver.page_source)

# Parse the page source with BeautifulSoup
soup = BeautifulSoup(driver.page_source, 'html.parser')

# print(str(soup))

# Find all the URLs on the page
urls = list(set([a['href'] for a in soup.find_all('a', href=True)]))

print(urls);

# Loop through the URLs
for url in urls:
    if not url.startswith('/u/'):
      continue

    if url in completed_urls:
      continue

    print(root+url)

    try:
      # Open the page
      driver.get(root+url+"?rerender=1")

      # Wait for the component to load
      wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Error')] | //div[@id='web-preview'][child::*]")))

      print("SUCCESS: "+url)
      # Add a delay to ensure the page has fully loaded (adjust as needed)
      # time.sleep(5)
      # Read the completed URLs from the file if it exists

      # Add the completed URL to the array
      completed_urls.append(url)

      # Save the completed URLs to the file
      with open('./completed_urls', 'w') as file:
        file.write('\n'.join(completed_urls))
    except Exception as e:
      print(e)
      print("Error: "+url)
      continue

# Close the WebDriver
driver.quit()