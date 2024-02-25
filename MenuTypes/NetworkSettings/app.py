from flask import Flask, request
import subprocess

app = Flask(__name__)

flag = True


@app.route("/")
def __password_input():
    if flag:
        return """<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Wi-Fi Configuration</title>
    </head>
    <body>
        <h1>Wi-Fi Configuration</h1>
        <form action="/set-password" method="post">
            <label for="password">Wi-Fi Password:</label>
            <input type="password" id="password" name="password" required>
            <br>
            <input type="submit" value="Submit">
        </form>
    </body>
    </html>"""
    else:
        return "Wi-Fi already configured"


@app.route("/set-password", methods=["POST"])
def __set_password():
    global flag
    if flag:
        subprocess.run(f"echo Pw:{request.form['password']}", shell=True)
        flag = False
        return "Wi-Fi successfully configured"
    else:
        return "Wi-Fi already configured"
