#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from flask import Flask, render_template, redirect, request, Response
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sys
from pprint import pprint
import time
import threading
import queue
import json
from waveshare_epd import epd4in2b_V2

host="0.0.0.0"
port=8080

epd = epd4in2b_V2.EPD()

ALLOWED_EXTENSIONS_GENERAL=set(['png', 'jpg', 'jpeg'])
ALLOWED_EXTENSIONS_PREPARED=set(['bmp'])


### HELPERS
def allowed_file(filename, allow_list):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in allow_list



application = Flask(__name__)
@application.route('/')
def index():
    return render_template('index.html')

@application.route('/loader')
def loader():
    return render_template('loader.html')

@application.route('/loader', methods=['POST'])
def loaderUpload():
    if ('file_b' not in request.files) or ('file_r' not in request.files):
        print("No image in request")
        return 'No image in request',400
    
    pprint(request.files)

    files = {}
    for file in request.files:
        if request.files[file].filename != '' and allowed_file(request.files[file].filename, ALLOWED_EXTENSIONS_PREPARED):
          files[file] = request.files[file]

    print(files)
    if len(files) == 0:
        print("No file selected or invalid file type")
        return 'No file selected or invalid file type',400

    return redirect(request.url)




@application.route('/converter')
def converter():
    return render_template('converter.html')

application.run(host=host, port=port)




