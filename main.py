## Imports
from fastapi import FastAPI
from fastapi.responses import FileResponse

from nicegui import ui

import uvicorn as uv

import sqlite3 as sql

import datetime as dt
import qrcode
import csv
import io
import os


## Config
DB_PATH = os.environ.get(
    'DB_PATH',
    'tamu_crew_attendance.db'
)
ROOT_URL = os.environ.get(
    'ROOT_URL',
    'http://localhost:8000'
)
STORAGE_SECRET = os.environ.get(
    'STORAGE_SECRET',
    'dev-secret'
)
todays_password = False
ROOT_URL = "tbd"
QR_PATH = 'attendance_qr.png'

qr = qrcode.make(ROOT_URL)
qr.save(QR_PATH)


## Database
db = sql.connect(DB_PATH, check_same_thread=False)
cursor = db.cursor()


## Schema
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    squad TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    status TEXT NOT NULL DEFAULT "N",
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, attendance_date)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS passwords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    password TEXT NOT NULL,
    date DATE NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password TEXT NOT NULL
)
""")

cursor.execute("""
INSERT INTO admin (username, password) 
VALUES ('tamucrew', 'crewcest')
""")
db.commit()


## Business Logic & Helper Functions
def get_date():
  return dt.datetime.now().strftime("%Y-%m-%d")

def get_user(name,squad):
  cursor.execute("SELECT * FROM users WHERE name = ? AND squad = ?", (name, squad))
  return cursor.fetchone()

def get_all_users():
  cursor.execute("""
      SELECT name, squad
      FROM users
      ORDER BY name
  """)

  return cursor.fetchall()

def add_user(name, squad):
  name = name.lower()
  name = name.strip()
  squad = squad.lower()
  squad = squad.strip()

  if get_user(name,squad) is None:
    cursor.execute("INSERT INTO users (name, squad) VALUES (?, ?)", (name, squad))
    db.commit()
    return True
  else:
    return False

def get_user_id(name):
  name = name.lower()
  name = name.strip()

  cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
  result = cursor.fetchone()

  if result is None:
    return False
  else:
    return result[0]

def sign_in(name):
  user_id = get_user_id(name)

  if user_id is False:
    return False
  else:
    try:
      cursor.execute("INSERT INTO attendance (user_id, attendance_date, status) VALUES (?, ?, ?)", (user_id, get_date(), "Y"))
      db.commit()
      return True
    except sql.IntegrityError:
      return "-1"

def get_attendance_today():
  cursor.execute("SELECT * FROM attendance WHERE attendance_date = ?", (get_date(),))
  return cursor.fetchall()

def set_day_password(password):
  cursor.execute("INSERT INTO passwords (password, date) VALUES (?, ?)", (password, get_date()))
  db.commit()
  ui.notify('Password Set')

def check_password(password):
  cursor.execute("SELECT * FROM passwords WHERE password = ? AND date = ?", (password, get_date()))
  result = cursor.fetchone()

  if result is None:
    return False
  else:
    return True

def check_admin(username, password):
  cursor.execute("SELECT * FROM admin WHERE username = ? AND password = ?", (username, password))
  result = cursor.fetchone()

  if result is None:
    return False
  else:
    return True
  
async def bulk_user_upload(e):
  content = await e.file.read()
  text = content.decode('utf-8')
  reader = csv.DictReader(io.StringIO(text))
  added = 0
  skipped = 0

  for row in reader:
    name = row.get('name')
    squad = row.get('squad')

    if not name or not squad:
      skipped += 1
      continue

    result = add_user(name.strip(),squad.strip())

    if result:
        added += 1
    else:
        skipped += 1

  ui.notify(f'Added {added} users; skipped {skipped}')

def attendance_query(period):
  today = dt.datetime.now().date()

  # -----------------------------------------
  # TODAY
  # Every user gets a row for today.
  # If they have no attendance record -> N
  # -----------------------------------------
  if period == 'Today':

      cursor.execute("""
          SELECT
              u.name,
              u.squad,
              ? AS attendance_date,
              COALESCE(a.status, 'N') AS status

          FROM users AS u

          LEFT JOIN attendance AS a
              ON a.user_id = u.id
              AND a.attendance_date = ?

          ORDER BY u.name
      """, (str(today), str(today)))

  # -----------------------------------------
  # THIS WEEK
  # Use attendance dates that actually exist
  # during the current week.
  # -----------------------------------------
  elif period == 'This Week':

      start_date = today - dt.timedelta(
          days=today.weekday()
      )

      cursor.execute("""
          WITH dates AS (
              SELECT DISTINCT attendance_date
              FROM attendance
              WHERE attendance_date BETWEEN ? AND ?
          )

          SELECT
              u.name,
              u.squad,
              d.attendance_date,
              COALESCE(a.status, 'N') AS status

          FROM users AS u

          CROSS JOIN dates AS d

          LEFT JOIN attendance AS a
              ON a.user_id = u.id
              AND a.attendance_date = d.attendance_date

          ORDER BY
              d.attendance_date,
              u.name
      """, (str(start_date), str(today)))

  # -----------------------------------------
  # ALL TIME
  # Use every date where attendance was taken.
  # -----------------------------------------
  elif period == 'All Time':

      cursor.execute("""
          WITH dates AS (
              SELECT DISTINCT attendance_date
              FROM attendance
          )

          SELECT
              u.name,
              u.squad,
              d.attendance_date,
              COALESCE(a.status, 'N') AS status

          FROM users AS u

          CROSS JOIN dates AS d

          LEFT JOIN attendance AS a
              ON a.user_id = u.id
              AND a.attendance_date = d.attendance_date

          ORDER BY
              d.attendance_date,
              u.name
      """)

  else:
      return []

  return cursor.fetchall()

def export_attendance_csv(period):
    rows = attendance_query(period)

    file_path = '/content/attendance_export.csv'

    with open(
        file_path,
        'w',
        newline='',
        encoding='utf-8'
    ) as f:

        writer = csv.writer(f)

        writer.writerow([
            'Name',
            'Squad',
            'Date',
            'Status'
        ])

        writer.writerows(rows)

    return file_path


## Fast API App & QR Page
fastapi_app = FastAPI()
@fastapi_app.get('/download-qr')
def download_qr():
  return FileResponse(
      QR_PATH,
      media_type='image/png',
      filename='attendance_qr.png'
  )


## NiceGUI Pages

#### Landing Page
@ui.page('/')
def pw_page() -> None:

  def handle_login(pw) -> None:
    if check_password(pw):
      ui.navigate.to('/attendance')
    else:
      ui.notify('Incorrect Password')


  with ui.header().style('background-color: #500000;'):
    ui.label(f"Texas A&M Crew Attendance").classes('text-2xl').style('color: white;')

  with ui.column().classes('absolute-center items-center'):
    pw_in = ui.input('Password', password=True)
    ui.button('Login', on_click = lambda: handle_login(pw_in.value))

  with ui.footer().style('background-color: #500000;'):
    ui.link('Coaches Login', '/coaches').classes('content-center').style('color: white;')
    ui.space()
    ui.link('Download QR Code','/download-qr').style('color: white;')

#### Sign-In Page
@ui.page('/attendance')
def attendance_page() -> None:

  def handle_sign_in(name) -> None:
    if sign_in(name):
      ui.notify('Signed In')
      ui.timer(3, lambda: ui.navigate.to('/'), once=True)
    elif sign_in(name) == "-1":
      ui.notify('Already Signed In')
      ui.timer(3, lambda: ui.navigate.to('/'), once=True)
    else:
      ui.notify('User Does Not Exist')

  with ui.header().style('background-color: #500000;'):
    ui.label(f"Texas A&M Crew Attendance").classes('text-2xl').style('color: white;')

  with ui.column().classes('absolute-center items-center'):
    ui.label('Sign In').classes('text-2xl')
    name_in = ui.input('Name')
    ui.button('Sign In', on_click=lambda: handle_sign_in(name_in.value))
    

  with ui.footer().style('background-color: #500000;'):
    ui.link('Coaches Login', '/coaches').classes('content-center').style('color: white;')

#### Coach Sign-In Page
@ui.page('/coaches')
def coaches_page() -> None:
  def handle_admin_login() -> None:
    if check_admin(un.value, pw.value):
      ui.navigate.to('/dashboard')
    else:
      ui.notify('Incorrect Username or Password')

  with ui.column().classes('absolute-center items-center'):
    ui.label('Username').classes('text-2xl')
    un = ui.input('Username')
    ui.label('Password').classes('text-2xl')
    pw = ui.input('Password', password=True)

    pw.on('keydown.enter', handle_admin_login)

    ui.button('Login', on_click=handle_admin_login)

#### Coach Dashboard
@ui.page('/dashboard')
def dashboard_page() -> None:
  def logout() -> None:
    ui.navigate.to('/')

  def set_password(new_pw) -> None:
    global todays_password
    todays_password = new_pw
    set_day_password(new_pw)

  def handle_add_user(name, squad) -> None:
    if add_user(name, squad):
      ui.notify('User Added')
    else:
      ui.notify('User Already Exists')

  def handle_export(period):
    path = export_attendance_csv(period.value)
    ui.download(path)

  with ui.header().style('background-color: #500000;'):
    ui.label(f"Texas A&M Crew Attendance").classes('text-2xl').style('color: white;')
    ui.space()
    ui.button('Logout', on_click=logout)

  with ui.grid(columns=2).classes('w-full h-[calc(100vh-64px)] gap-4 p-4'):

    with ui.card().classes('w-full h-full items-center justify-center'): ## Quadrant 1
      ui.label(f"Set Password For Today").classes('text-2xl')
      pw_in = ui.input('Password')
      pw_in.on('keydown.enter', lambda: set_password(pw_in.value))
      ui.button('Set Password', on_click=lambda: set_password(pw_in.value))

    with ui.card().classes('w-full h-full items-center justify-center'): ## Quadrant 2
      ui.label(f"Add Team Member").classes('text-2xl')
      name_in = ui.input('Name')
      squad_in = ui.input('Squad')
      ui.button('Add', on_click=lambda: handle_add_user(name_in.value, squad_in.value))

    with ui.card().classes('w-full h-full items-center justify-center'): ## Quadrant 3
      ui.label(f"Bulk Upload Users (CSV)").classes('text-2xl')
      ui.label(f"Format: [name|squad]").classes('text-xl')
      ui.upload(
        label='Upload CSV',
        on_upload = bulk_user_upload,
        auto_upload=True
      ).props('accept=.csv')

    with ui.card().classes('w-full h-full items-center justify-center'): ## Quadrant 4
      ui.label('Export Attendance').classes('text-2xl font-bold')
      export_period = ui.select([
              'Today',
              'This Week',
              'All Time'
          ], value='Today', label='Export Range')

      ui.button('Download CSV', on_click=lambda:handle_export(export_period))

  with ui.footer().style('background-color: #500000;'):
    ui.link('List All Users', '/users').style('color: white;')

#### User List Page
@ui.page('/users')
def users_page() -> None:
  with ui.header().style('background-color: #500000;'):
      with ui.row().classes('w-full items-center'):

          ui.label(
              'Texas A&M Crew Attendance'
          ).classes('text-2xl').style('color: white;')

          ui.space()

          ui.link(
              'Back to Dashboard',
              '/dashboard'
          ).style('color: white;')

  users = get_all_users()

  with ui.column().classes('w-full p-6'):

      ui.label(
          'All Users'
      ).classes('text-3xl font-bold')

      ui.label(
          f'{len(users)} total users'
      ).classes('text-lg')

      ui.separator()

      for name, squad in users:
          with ui.row().classes(
              'w-full justify-between items-center'
          ):
              ui.label(name)
              ui.label(squad)

          ui.separator()


## Startup
ui.run_with(
    fastapi_app,
    storage_secret=STORAGE_SECRET
)

if __name__ in {'__main__', '__mp_main__'}:
    import uvicorn

    port = int(os.environ.get('PORT', 8000))

    uvicorn.run(
        fastapi_app,
        host='0.0.0.0',
        port=port
    )
