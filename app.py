from flask import Flask, render_template, request, redirect, url_for
from serpapi.google_search import GoogleSearch
import googleapiclient.discovery
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
import pycountry

app = Flask(__name__)

# Replace with your API keys
YOUTUBE_API_KEY = "AIzaSyAFyaAQp-cFs9K6C1EzJtTE7GaibUmLsAw"  # Your YouTube Data API v3 key
SERP_API_KEY = "7d70d4fca0d3a38b50ed0a596ad68b4c1b2cf1b487db1d28e9abdbabd91ef040"  # Your SERP API key

# Initialize the YouTube API client
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_channels(keyword, max_results=10):
    request = youtube.search().list(q=keyword, part="snippet", type="channel", maxResults=max_results)
    return request.execute()['items']

def get_channel_details(channel_id):
    request = youtube.channels().list(part="snippet,statistics,brandingSettings", id=channel_id)
    return request.execute()['items'][0]

def search_social_media_links(channel_name):
    params = {
        "engine": "google",
        "q": f"{channel_name} Instagram OR Twitter OR Facebook OR LinkedIn OR Website",
        "api_key": SERP_API_KEY,
    }
    try:
        return [result['link'] for result in GoogleSearch(params).get_dict().get('organic_results', [])]
    except Exception as e:
        print(f"Error searching links: {e}")
        return []

def search_contact_email(channel_name):
    params = {"engine": "google", "q": f"{channel_name} contact email", "api_key": SERP_API_KEY}
    try:
        results = GoogleSearch(params).get_dict()
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                           " ".join([f"{r.get('title','')} {r.get('snippet','')}" 
                                    for r in results.get('organic_results',[])]))
        return emails[0] if emails else "Not found"
    except Exception as e:
        print(f"Email search error: {e}")
        return "Not found"

def get_country_full_name(country_code):
    try:
        return pycountry.countries.get(alpha_2=country_code).name
    except:
        return "N/A"

def write_to_google_sheet(data, sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        r'C:\Users\anike\OneDrive\Desktop\Python Projects\my-youtube-api-project-449517-2eb9b32302b9.json', scope)  # Add Your JSON file Path Here...
    client = gspread.authorize(creds)  # Use 'client' for clarity
    try:
        sheet = client.open(sheet_name).sheet1
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: Spreadsheet '{sheet_name}' not found.")  # Handle spreadsheet not found
        return

    headers = [
        "Channel Name", "Channel URL", "Subscribers", "Total Views",
        "Video Count", "Join Date", "Country", "Channel Description",
        "Instagram", "Twitter", "Facebook", "LinkedIn", 
        "Other Links", "Email"
    ]

    # Check for headers more reliably.  Get the first row.
    first_row = sheet.row_values(1)  # Get the first row's values

    if not first_row or first_row != headers:  # Check if the first row exists AND if it matches the headers
        if first_row:  # Clear the first row if it exists but is incorrect
            sheet.delete_rows(1)
        sheet.insert_row(headers, 1)  # Insert headers at the beginning

    sheet.append_row(data)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        keyword = request.form.get("keyword")
        max_results = int(request.form.get("max_results"))
        sheet_name = request.form.get("sheet_name")

        for channel in search_channels(keyword, max_results):
            channel_id = channel['id']['channelId']
            details = get_channel_details(channel_id)
            snippet = details['snippet']
            stats = details['statistics']

            # Extract core data
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

            # Add social links and email
            channel_data.extend([
                socials['Instagram'],
                socials['Twitter'],
                socials['Facebook'],
                socials['LinkedIn'],
                ", ".join(other_links) if other_links else "Not found",
                search_contact_email(snippet['title'])
            ])

            write_to_google_sheet(channel_data, sheet_name)
            print(f"Processed: {snippet['title']}")

        return redirect(url_for("index"))

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=False)
