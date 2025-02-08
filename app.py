from flask import Flask, render_template, request, redirect, url_for
from serpapi.google_search import GoogleSearch
import googleapiclient.discovery
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import os
import pycountry

app = Flask(__name__)

# API Keys (Stored in Environment Variables for Security)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
SERP_API_KEY = os.environ.get("SERP_API_KEY")

# Google Sheet ID (Replace with your actual Google Sheet ID)
SHEET_ID = "1G1r-BGiPXV9j3qQzxjhWnLAS1j5PW8-eJjyHev6Zol8"  

# Initialize YouTube API client
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_channels(keyword, max_results=10):
    """Search for YouTube channels by keyword."""
    try:
        request = youtube.search().list(q=keyword, part="snippet", type="channel", maxResults=max_results)
        response = request.execute()
        print(f"✅ Found {len(response.get('items', []))} channels for '{keyword}'")  
        return response.get('items', [])
    except Exception as e:
        print(f"❌ Error fetching YouTube channels: {e}")
        return []

def get_channel_details(channel_id):
    """Fetch details for a YouTube channel."""
    try:
        request = youtube.channels().list(part="snippet,statistics,brandingSettings", id=channel_id)
        return request.execute()['items'][0]
    except Exception as e:
        print(f"❌ Error fetching channel details: {e}")
        return {}

def search_social_media_links(channel_name):
    """Find social media links using Google Search."""
    params = {
        "engine": "google",
        "q": f"{channel_name} Instagram OR Twitter OR Facebook OR LinkedIn OR Website",
        "api_key": SERP_API_KEY,
    }
    try:
        results = GoogleSearch(params).get_dict().get('organic_results', [])
        return [result['link'] for result in results]
    except Exception as e:
        print(f"❌ Error searching social links: {e}")
        return []

def search_contact_email(channel_name):
    """Find email contact for a channel."""
    params = {"engine": "google", "q": f"{channel_name} contact email", "api_key": SERP_API_KEY}
    try:
        results = GoogleSearch(params).get_dict()
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                            " ".join([f"{r.get('title','')} {r.get('snippet','')}" 
                                      for r in results.get('organic_results',[])]))
        return emails[0] if emails else "Not found"
    except Exception as e:
        print(f"❌ Email search error: {e}")
        return "Not found"

def get_country_full_name(country_code):
    """Convert country code to full name."""
    try:
        return pycountry.countries.get(alpha_2=country_code).name
    except:
        return "N/A"

def write_to_google_sheet(data):
    """Store extracted data in Google Sheets using Sheet ID."""
    print(f"📌 Writing data to Google Sheet ID: {SHEET_ID}")  

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds_dict = {
        "type": "service_account",
        "project_id": os.environ.get("GOOGLE_PROJECT_ID"),
        "private_key_id": os.environ.get("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.environ.get("GOOGLE_PRIVATE_KEY").replace('\\n', '\n'),
        "client_email": os.environ.get("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.environ.get('GOOGLE_CLIENT_EMAIL')}"
    }

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SHEET_ID).sheet1  # Open using Google Sheet ID

        print("✅ Connected to Google Sheets.")  

        headers = [
            "Channel Name", "Channel URL", "Subscribers", "Total Views",
            "Video Count", "Join Date", "Country", "Channel Description",
            "Instagram", "Twitter", "Facebook", "LinkedIn", 
            "Other Links", "Email"
        ]

        # Ensure headers exist
        first_row = sheet.row_values(1)
        if not first_row or first_row != headers:
            if first_row:  
                sheet.delete_rows(1)  # Remove incorrect headers
            sheet.insert_row(headers, 1)  
            print("✅ Headers added.")  

        print(f"📌 Writing data: {data}")  
        sheet.append_row(data)
        print("✅ Data added to Google Sheets!")  

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Error: Spreadsheet not found.")  
    except Exception as e:
        print(f"❌ Error writing to Google Sheets: {e}")  

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        keyword = request.form.get("keyword")
        max_results = int(request.form.get("max_results"))

        print(f"📌 Searching YouTube for: {keyword}")  

        for channel in search_channels(keyword, max_results):
            channel_id = channel['id']['channelId']
            details = get_channel_details(channel_id)
            snippet = details['snippet']
            stats = details['statistics']

            channel_data = [
                snippet['title'],
                f"https://www.youtube.com/{snippet.get('customUrl', 'channel/'+channel_id)}",
                stats.get('subscriberCount', 'N/A'),
                stats.get('viewCount', 'N/A'),
                stats.get('videoCount', 'N/A'),
                snippet['publishedAt'],
                get_country_full_name(snippet.get('country', 'N/A')),
                snippet.get('description', 'N/A')
            ]

            # Process social links
            social_links = search_social_media_links(snippet['title'])
            socials = {
                'Instagram': 'Not found',
                'Twitter': 'Not found',
                'Facebook': 'Not found',
                'LinkedIn': 'Not found'
            }
            other_links = []

            for link in social_links:
                if 'instagram.com' in link: socials['Instagram'] = link
                elif 'twitter.com' in link or 'x.com' in link: socials['Twitter'] = link
                elif 'facebook.com' in link: socials['Facebook'] = link
                elif 'linkedin.com' in link: socials['LinkedIn'] = link
                else: other_links.append(link)

            channel_data.extend([
                socials['Instagram'],
                socials['Twitter'],
                socials['Facebook'],
                socials['LinkedIn'],
                ", ".join(other_links) if other_links else "Not found",
                search_contact_email(snippet['title'])
            ])

            write_to_google_sheet(channel_data)
            print(f"✅ Processed: {snippet['title']}")  

        return redirect(url_for("index"))

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=False)
