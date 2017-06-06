import requests                             # to make HTTPS requests
from bs4 import BeautifulSoup       # to parse HTML pages and scrape
import urllib2                                  # to open urls
from datetime import date               # to get the current time and date
import datetime
import pymysql.cursors                      # to save scraped data into MySQL
import smtplib                                      # to send emails to yourself incase of errors

def getDateTime():
# Gets current date and time    
    scrapeDateTime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    scrapeDateTime = scrapeDateTime.split(" ")
    date = scrapeDateTime[0]
    time = scrapeDateTime[1]
    return date, time

def openMySQLConnection():
    # connect to database
    connection = pymysql.connect(host='localhost',
                                 user='root',
                                 password = db_password,
                                 db = db_name ,
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)
    return connection

####### SECTION 1: Set Master Data - FILL THIS SECTION OUT #######

# URL of login page
URL="https://selfserve.publicmobile.ca/Overview/"

# Public Mobile credentials
username="ADD YOUR PUBLIC MOBILE ACCOUNT USER EMAIL HERE"
password="ADD YOUR PUBLIC MOBILE ACCOUNT PASSWORD HERE"
myAccountNumber = "OPTIONAL: ADD YOUR PUBLIC MOBILE ACCOUNT NUMBER HERE"

# MySQL Credentials
db_name = "ADD YOUR MYSQL DATABASE NAME HERE (user is assumed to be 'root' - change if yours differs)"
db_password = "ADD YOUR MYSQL PASSWORD HERE"

# My Email credentials
email = "ADD YOUR SMPT EMAIL ADDRESS HERE"
email_password = "ADD YOUR SMPT EMAIL PASSWORD HERE"
smpt_server = "ADD YOUR SMPT EMAIL SERVER HERE (e.g. smpt.gmail.com)"

# Path to local intermediate certificate for successful SSL/HTTPS request - see my github page for the certificate
cacert = "ADD PATH TO THE INTERMEDIATE CERTIFICATE HERE"

# set header to spoof browser
headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64; rv:44.0) Gecko/20100101 Firefox/44.0 Iceweasel/44.0.2"}

# Save current date and time 
dateTimeList = getDateTime()
date = dateTimeList[0]
time = dateTimeList[1]


####### SECTION 2: Get page and parse it to extract form data for login #######

# create a request session for cookies
s = requests.Session()
# update session header
s.headers.update(headers)

# Public Mobile's website is missing the intermediate SSL certificate
# therefore a reference to a local intermed. cert. is necessary
# to download cert. go here https://cryptoreport.websecurity.symantec.com/checker/ or check my github page
# to bundle cert. into pem file install certifi module and run "python -c import certifi; print(certifi.where())" and add file
r = s.get(URL, verify=cacert)
# For de-bugging, check status of server response through r.status_code


####### SECTION 3: Error handling; In case script does not land on the PM account page e.g. due to maintenance #######

# Uncomment to test error handling (for DB)
# r.url = "wrong_page.ca/test"

if r.url != URL:

    print "Something went wrong (check r.url)"
    
    # save r.url to insert into db
    errorURL = r.url

    # If errorURL is NOT the maintenance URL, notify yourself through email immediately so you can investigate the issue
    if errorURL != 'https://publicmobile.ca/en/on/maintenance':

        SUBJECT = "PM Data Scraping FATAL error"
        msg = errorURL
        #send me email
        message = 'Subject: {}\n\n{}'.format(SUBJECT, msg)
    
        # Connect to SMTP server and send email
        server = smtplib.SMTP(smpt_server, 587)
        server.starttls()
        server.login(email, email_password)
        server.sendmail(email, email, message)
        server.quit()

    # connect to database function to log errorURL
    connection = openMySQLConnection()

    try:
        with connection.cursor() as cursor:
            # Run SQL Insertion code (Note errorURL is NULL)
            sql = "INSERT INTO `data_usage_history` (`dateS`,`timeS`,`dataUsed`,`errorURL`,`accountNumber`) VALUES (%s, %s, NULL, %s, %s)"
            cursor.execute(sql, (date, time, errorURL, str(myAccountNumber)))
        connection.commit()

    finally:
        connection.close()


else:

    ####### SECTION 4: Perform account login and scrape for the data usage balance #######        

    # load HTML DOM into beautiful soup
    soup = BeautifulSoup(r.content, 'html.parser')

    # extract form data required for a successful login from soup
    VIEWSTATE = soup.find(id="__VIEWSTATE")['value']
    EVENTVALIDATION = soup.find(id="__EVENTVALIDATION")['value']
    EVENTTARGET = soup.find(id="__EVENTTARGET")['value']
    EVENTARGUEMENT = soup.find(id="__EVENTARGUMENT")['value']
    VIEWSTATEGENERATOR = soup.find(id="__VIEWSTATEGENERATOR")['value']
    VIEWSTATEENCRYPTED = soup.find(id="__VIEWSTATEENCRYPTED")['value']

    # create the login data object based on extraction
    login_data = {
    "--EVENTARGUEMENT":EVENTARGUEMENT,
    "__EVENTTARGET":EVENTTARGET,    
    "__VIEWSTATE":VIEWSTATE,
    "__VIEWSTATEGENERATOR": VIEWSTATEGENERATOR,
    "__VIEWSTATEENCRYPTED": VIEWSTATEENCRYPTED,
    "__EVENTVALIDATION":EVENTVALIDATION,
    "ctl00$FullContent$ContentBottom$LoginControl$UserName":username,
    "ctl00$FullContent$ContentBottom$LoginControl$Password":password,
    "ctl00$FullContent$ContentBottom$LoginControl$chkRememberUsername":"on",
    "ctl00$FullContent$ContentBottom$LoginControl$LoginButton":"Log In",
    }

    # make the post request with login data to login
    r = s.post(URL, data=login_data, verify=cacert)
    r = s.get("https://selfserve.publicmobile.ca/Overview/", verify=cacert)


    # find a list of all span elements with id "VoiceUsedLiteral"
    soup = BeautifulSoup(r.text, 'html.parser')
    myDataUsage = soup.find('span', {'id': 'VoiceUsedLiteral'}).text
    myDataLimit = soup.find('span', {'id': 'VoiceAllowanceLiteral'}).text


    # de-bugging: print scraped result to terminal
    print "\n"
    print "-----------------------------------------"
    print 'Total mb used this period for Account #%s: %s/%s' %(myAccountNumber, myDataUsage, myDataLimit)
    print "-----------------------------------------"


    ####### SECTION 5: Insert scraped data usage level into MySQL database #######        

    # cal function to start database connection
    connection = openMySQLConnection()

    try:
        with connection.cursor() as cursor:
            # Run SQL Insertion code
            sql = "INSERT INTO `data_usage_history` (`dateS`,`timeS`,`dataUsed`, `errorURL`, `accountNumber`) VALUES (%s, %s, %s, NULL, %s)"
            cursor.execute(sql, (date, time, myDataUsage, str(myAccountNumber)))
        connection.commit()

    finally:
        connection.close()
