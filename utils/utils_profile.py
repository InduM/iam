import base64

def decode_base64_image(data):
    return base64.b64decode(data) if data else None
