# coding=utf-8

import os
import requests
from flask import Flask, request, json, abort
from google.cloud import firestore
import base64

app = Flask(__name__)

db = firestore.Client()
api_url = "https://graph.facebook.com/v8.0"


@app.route('/', methods=['GET', 'POST'])
def main():
    return chatbot(request)


steps = {
    "step-1": {"type": "options",
               "message": [
                   {
                       "title": "Comprar un telefono",
                       "image_url": "https://images.freeimages.com/images/large-previews/041/mobiles-1224386.jpg",
                       "subtitle": "Selecciona uno de nuestros equipos",
                       "buttons": [
                           {
                               "type": "postback",
                               "title": "Telefonos",
                               "payload": "step-2"
                           }
                       ]
                   }, {
                       "title": "Contratar un plan",
                       "image_url": "https://images.freeimages.com/images/large-previews/5c9/signing-the-contract-1512122.jpg",
                       "subtitle": "No te quedes incomunicado",
                       "buttons": [
                           {
                               "type": "postback",
                               "title": "Planes",
                               "payload": "step-2"
                           }
                       ]
                   }, {
                       "title": "Soporte",
                       "image_url": "https://images.freeimages.com/images/large-previews/aad/help-1192586.jpg",
                       "subtitle": "Hablar con un ejecutivo",
                       "buttons": [
                           {
                               "type": "postback",
                               "title": "Soporte",
                               "payload": "step-99"
                           }
                       ]
                   }]
               },
    "step-99": {
        "type": "text",
        "message": "en un momento uno de nuestros ejecutivos te atendera"
    }
}


def chatbot(request):
    if request.method == "GET":
        # cuando el endpoint este registrado como webhook, debe mandar de vuelta
        # el valor de 'hub.challenge' que recibe en los argumentos de la llamada
        if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
            if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
                return "Verification token mismatch", 403
            return request.args["hub.challenge"], 200
        abort(418)

    elif request.method == "POST":

        # procesar los mensajes que llegan

        data = request.get_json()
        # print(json.dumps(data, indent=2))

        if data["object"] == "page":

            for entry in data["entry"]:

                for messaging_event in entry["messaging"]:

                    data = {"recipient":
                                {"id": messaging_event["sender"]["id"]
                                 },
                            "message": {}
                            }

                    # vamos a revisar si el usuario ya ha usado el chatbot antes y obtener el paso donde se quedo

                    message = ""
                    if messaging_event.get("message"):  # alguien envia un mensaje
                        message = messaging_event["message"]["text"]  # el texto del mensaje

                    elif messaging_event.get("postback"):  # evento cuando usuario hace click en botones
                        message = messaging_event["postback"][
                            "payload"]  # el payload del boton (mensaje al backend no el label del boton)
                    print("incoming message: {msg}".format(msg=message))

                    status = get_status(str(messaging_event["sender"]["id"]))

                    if status["step"] == "step-0" or message == "step-0":
                        welcome(data, status)

                    elif message.startswith("step-"):
                        get_msg(data, message)

                    else:
                        default_msg(data)

        return "ok"

    else:
        abort(418)


def welcome(data, status):
    content = {"message": "Hola {name} soy un bot selecciona una opción de las que se muestran a continuación".format(
        name=status["first_name"]),
        "type": "text"}
    set_status(data["recipient"]["id"], "step-1")
    send_message(data, content)
    get_msg(data, "step-1")


def default_msg(data):
    send_message(data, {"message": "No puedo entender tu petición", "type": "text"})


def get_msg(data, step):
    if step in steps:
        print(steps[step])
        send_message(data, steps[step])
        set_status(data["recipient"]["id"], step)
    else:
        default_msg(data)


def set_status(id, step):
    try:
        db.collection('users').document(tobase64(id)).update({"step": step});
    except:
        print("is not posible to set the step on the user {id}".format(id=id))


def get_status(id):
    # nos ayuda a que los queries no sean lexicologicamente cercanos
    iddoc = tobase64(id)
    user = db.collection('users').document(iddoc)
    doc = user.get()
    if doc.exists:
        print("User {id} found".format(id=id))
        data = doc.to_dict()

    else:
        print("Creating user profile")
        data = get_user_data(id)
        data["step"] = "step-0"
        user.set(data)

    print(data)
    return data


def tobase64(stx):
    return str(base64.b64encode(bytes(stx, 'utf-8')).decode("utf-8"))


def get_user_data(user):
    response = requests.get(
        "{fb_api}/{user}?fields=first_name,gender,locale&access_token={token}"
            .format(fb_api=api_url, user=user, token=os.environ["PAGE_ACCESS_TOKEN"]))
    response = json.loads(response.content)
    del response["id"]
    return (response)


def send_message(data, content):
    try:
        del data["message"]["text"]
        del data["message"]["attachment"]
    except:
        pass

    if content["type"] == "text":
        data["message"]["text"] = content["message"]

    elif content["type"] == "options":
        data["message"]["attachment"] = {"type": "template",
                                         "payload": {
                                             "template_type": "generic",
                                             "elements": content["message"]
                                         }
                                         }

    data = json.dumps(data, indent=2)
    #print(data)  # ver detalles de los mensajes enviados

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }

    r = requests.post("{fb_api}/me/messages".format(fb_api=api_url), params=params, headers=headers, data=data)
    if r.status_code != 200:
        print(r.status_code)
        print(r.text)


if __name__ == '__main__':
    app.run(debug=True)
