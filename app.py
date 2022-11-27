#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from flask import Flask, render_template, redirect, request, Response, url_for
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sys
import os
from pprint import pprint
import time
import threading
import traceback
import queue
from waveshare_epd import epd4in2b_V2 as epd4in2b

host="0.0.0.0"
port=8080

epd = epd4in2b.EPD()
displayQueue = queue.Queue()

ALLOWED_EXTENSIONS_GENERAL=set(['png', 'jpg', 'jpeg'])
ALLOWED_EXTENSIONS_PREPARED=set(['bmp'])


### HELPERS
def allowed_file(filename, allow_list):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in allow_list

def refByMiddle(w, h, text, font_data):
    size = font_data.getsize(text)

    return(w - (size[0]/2), h - (size[1]/2), text, font_data)

####
# Basic image functionality
####

# Loader for pre converted images

def load_prepared_image(loadedFiles):
    if "file_b" in loadedFiles:
        image_b = Image.open(loadedFiles["file_b"])
    else:
        image_b = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)

    if "file_r" in loadedFiles:
        image_r = Image.open(loadedFiles["file_r"])
    else:
        image_r = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)
    return image_b, image_r

def convert_image(file, threshold, threshold_off, rotation, bicolor, invert):
    image_file = Image.open(file)
    size = (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT)
    if rotation != 0:
        image_file = image_file.rotate(rotation)
    image_file = ImageOps.fit(image_file, size, Image.HAMMING, centering=(0.0, 0.5))
    image_file = image_file.convert('L')
    image_b = image_file.point(lambda p: p > threshold and 255)
    if invert and not bicolor:
        image_b = ImageOps.invert(image_b)

    if bicolor:
        print("Bicolor is on")
        image_r = image_file.point(lambda p: p > threshold + threshold_off and 255)
        image_r = ImageOps.invert(image_r)
        return image_b, image_r

    image_r = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)
    return image_b, image_r

def push_image(pic, swap=False):
    image_b = pic[0].convert('L')
    image_r = pic[1].convert('L')

    if swap:
        image_b, image_r = image_r, image_b

    try:
        epd = epd4in2b.EPD()
        epd.init()
        epd.display(epd.getbuffer(image_b), epd.getbuffer(image_r))
        epd.sleep()
    except:
        print('traceback.format_exc():\n%s', traceback.format_exc())
        epd = epd4in2b.EPD()
        epd.sleep()
        exit()

def clear_screen():
    epd.init()
    epd.Clear()
    epd.sleep()


def queue_handler():
    while True:
        try:
            job = displayQueue.get()
            if job["type"] == "load":
                print("Show pre-processed image")

                push_image(load_prepared_image(job["loadedFiles"]))
                for file in job["loadedFiles"]:
                    os.remove(job["loadedFiles"][file])

                print("Image displayed")
            elif job["type"] == "clear":
                print("Clear Screen")

                clear_screen()

                print("Screen cleared")
            elif job["type"] == "convert":
                print("Convert image")
                file = job["file"]
                threshold = int(job["options"]["threshold"])
                threshold_off = int(job["options"]["threshold_off"])
                rotation = int(job["options"]["rotation"])
                if "bicolor" in job["options"]:
                    bicolor = True
                else:
                    bicolor = False
                if "swap" in job["options"]:
                    swap = True
                else:
                    swap = False
                if "invert" in job["options"]:
                    invert = True
                else:
                    invert = False
                
                picture = convert_image(file=file,
                                    threshold=threshold,
                                    bicolor=bicolor,
                                    threshold_off=threshold_off,
                                    rotation=rotation,
                                    invert=invert)
                push_image(picture, swap)
                
                print("Image displayed")
            else:
                pass
        except:
          print('traceback.format_exc():\n%s', traceback.format_exc())
          continue
        time.sleep(10)


     
####
# Web-Interface
####
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
        print("No file in request")
        return 'No file in request',400
    files = {}
    for file in request.files:
        if request.files[file].filename != '' and allowed_file(request.files[file].filename, ALLOWED_EXTENSIONS_PREPARED):
          files[file] = request.files[file]
    if len(files) == 0:
        print("No file selected or invalid file type")
        return 'No file selected or invalid file type',400

    job = {}
    job["loadedFiles"] = {}
    for file in files:
        files[file].save(os.path.join("images/", files[file].filename))
        job["loadedFiles"][file] = os.path.join("images/", files[file].filename)
    job["type"] = "load"
    displayQueue.put(job)
    return redirect(request.url)




@application.route('/converter')
def converter():
    return render_template('converter.html')

@application.route('/converter', methods=['POST'])
def converterUpload():
    if 'file' not in request.files:
        print("No file in request")
        return 'No file in request',400
    file = request.files['file']
    if file.filename != '' and allowed_file(file.filename, ALLOWED_EXTENSIONS_GENERAL):
        file.save(os.path.join("images/", file.filename))
        job = {}
        job["file"] = os.path.join("images/", file.filename)
        job["options"] = request.form
        job["type"] = "convert"
        displayQueue.put(job)
        return redirect(request.url)
    else:
        print("No file selected or invalid file type")
        return 'No file selected or invalid file type',400

@application.route('/clear')
def clear():
    job = {"type": "clear"}
    displayQueue.put(job)
    return redirect("/")


threading.Thread(target=queue_handler).start()
application.run(host=host, port=port, debug=True)




