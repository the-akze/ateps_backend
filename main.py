from flask import Flask, send_file, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, send
import base64
import firebase_admin
from firebase_admin import credentials, db
import json
import os
import datetime
from time import time
import traceback


app = Flask(__name__)
CORS(app)
socketio = SocketIO(app)

print("initializing firebase...")
c = json.loads(os.environ['firebase_admin_certificate'])
cred = credentials.Certificate(c)
firebase_admin.initialize_app(cred, {
    'databaseURL':
    'https://ateps-97226-default-rtdb.firebaseio.com'
})
print("initialized firebase!")

@app.route("/")
def index():
    return "<style>* {font-family: Arial, sans-serif;}</style><h1>Hello</h1><br/><h3>This is the backend of ATEPS.</h3>"

@app.route("/streampage")
def streampage():
    return send_file("streampage.html")

def streamBase64(b64):
    try:
        socketio.emit("streamtoclient", {"data": str(b64)}, broadcast=True)
        return True
    except Exception as e:
        print("error happened", e)
        return False

@app.route("/stream", methods=["POST"])
def handleRouteStream():
    try:
        print(request.json)
        b64 = request.json["img"]
        return "success" if streamBase64(b64) else "error"
    except Exception as e:
        print("error happened", e)
        return "error"

@socketio.on("stream")
def handleStream(data):
    streamBase64(data)
    # socketio.emit("streamtoclient", data, broadcast=True, include_self=False)

@socketio.on("connect")
def on_connect(data):
    print("new client connected")


@app.route("/add_student", methods=["GET"])
def add_student_no_param():
    return jsonify({"status": "error", "message": "no student id provided"})


@app.route("/add_student/<string:id>", defaults={'id': ''})
@app.route("/add_student/<string:id>", methods=["GET", "POST"])
def add_student(id):
    print("request: add student")
    if (id == ''):
        return jsonify({
            "status": "error",
            "message": "no student id provided"
        })

    try:
        date_formatted = str(datetime.datetime.now())[0:10]
        n = ""
        try:
            n = get_student_name(id)
        except Exception as e:
            print("student may not exist in db error:", e)
            return jsonify({
                "status": "error",
                "message": "student may not exist in database"
            })
        obj = {"dates": {}, "name": n}
        obj["dates"][date_formatted] = {
            "time": time(),
            "state": 1
            # 0 = not here
            # 1 = here
            # 2 = late
        }
        print("obj", obj)
        t = db.reference("/classes/c1/time").get()
        if (obj["dates"][date_formatted]["time"] > t):
            obj["dates"][date_formatted]["state"] = 2
        ref = db.reference("/classes/c1/students/" + id)
        ref.update(obj)
        db.reference("/check").update({"lastScan": time() * 1000})
        
        return jsonify({
            "status": "success",
            "message": "updated student successfully",
            "student_name": n,
            "updated_content": obj
        })

    except Exception as e:
        print("error while updating student", e)
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": "error happened while updating student"
        })


def get_attendance_raw(class_id):
    ref = db.reference("/classes/" + class_id)
    return ref.get()


def get_attendance_table(class_id):
    with open("class_" + class_id + ".csv", "w") as class_csv:
        ref = db.reference("/classes/" + class_id)
        class_attendance = ref.get()
        print("reference get", class_attendance)
        students = class_attendance["student_members"]
        if str(type(students)) == "<class 'dict'>":
            students = list(students.values())

        s_col = students.copy()
        s_col.insert(0, "DATE")

        date_check = {}
        student_att = list(class_attendance["students"].values())

        # adding all the days that anyone has for their name
        for i in range(len(student_att)):
            for d in student_att[i]["dates"].keys():
                date_check[d] = student_att[i]
            date_check[list(student_att[i]["dates"].keys())[0]]

        matrix = [[0 for x in range(len(students) + 1)]
                  for y in range(len(date_check.keys()))]

        matrix.insert(0, s_col)

        dates = list(date_check.keys())
        for i in range(len(dates)):
            matrix[i + 1][0] = dates[i]

        print("students", students)
        cas = class_attendance["students"]
        for i in range(len(students)):
            current_student = students[i]
            if (not current_student in cas):
                print("current student", current_student, "not in attendance")
                continue
            print("current student", current_student)
            student_dates = cas[current_student]["dates"]
            for t in student_dates:
                try:
                    matrix[dates.index(t) + 1][i +
                                               1] = student_dates[t]["state"]
                except Exception as e:
                    print("ERROR!", e)
                    print("student that error", current_student)
                    print("student date that error", t)

        print("-- MATRIX --")
        print("\n".join([",".join([str(t) for t in i]) for i in matrix]))

        return matrix


@app.route("/get_attendance", methods=["GET"])
def get_attendance_request_no_param():
    return jsonify({"status": "error", "message": "no class id provided"})


@app.route('/', defaults={'id': ''})
@app.route("/get_attendance/<string:id>", methods=["GET", "POST"])
def get_attendance_request(id):
    if (id == ''):
        return jsonify({"status": "error", "message": "no class id provided"})

    m = get_attendance_table(id)
    return jsonify(m)

def get_student_name(id):
    ref = db.reference("student_ids/" + id)
    return ref.get()

if (__name__ == "__main__"):
    socketio.run(app, host="0.0.0.0", port="5000", debug=True)