# Crew Attendance Tracker
Lightweight attendance tracking web app designed for club rowing teams.


## About
Built in around 6 hours purely in Python using NiceGUI, FastAPI, & SQLite. I (willbg05) have had trouble shipping projects in the past because I would keep wanting to add new things until eventually the scale of the project was out of my grasp. I sat down with the goal to finish this project in one sitting, which I did (hooray!!!), but my code-cleanliness definitely wavered towards the end.

The app is designed with the intention that the coaches of a rowing (or any athletic organization) can take attendance by printing out a QR code and posting it in their facility. The code will take athletes to a sign-in page that will prompt the user to enter a password updated daily by the coaches (Ideally that password will be written down physically in the facility to prevent false sign-ins). Once the user has entered the password, they will be redirected to a page where they can submit their name; upon submission their attendance will be updated to "present".

Coaches have a separate admin sign-in panel which takes them to their own dashboard. From there, they can List all users currently on their roster, add new users in bulk by submitting a CSV, set the password for the day, and export the attendance data for the day, the week, or all-time.

Other clubs are welcome to adopt this, I tried to keep the code concise.

## Running Locally
Install the necessary files with:
```bash
pip install -r requirements.txt
python main.py
```
