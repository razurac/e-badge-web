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
import socket
from waveshare_epd import epd4in2b_V2 as epd4in2b

####
#  Setup
####

# Vars

defaults = {"location": [0,0],
            "font_file": "font/open-sans/bold.ttf",
            "text_size": 20}

config =   {"host": "0.0.0.0",
            "port": 8080,
            "ALLOWED_EXTENSIONS_GENERAL": set(['png', 'jpg', 'jpeg']),
            "ALLOWED_EXTENSIONS_PREPARED": set(['bmp'])}

# Objects

epd = epd4in2b.EPD()
displayQueue = queue.Queue()


####
# Helpers
####

# File helpers
def allowed_file(filename, allow_list):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in allow_list

# Image alignment helpers
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

# Converter for Images

def convert_image(file, threshold, threshold_off, rotation, bicolor, invert, dither):
    image = Image.open(file)
    size = (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT)
    image_b = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)
    image_r = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)
    if rotation == 90:
        image = image.transpose(Image.Transpose.ROTATE_90)
    elif rotation == 180:
        image = image.transpose(Image.Transpose.ROTATE_180)
    elif rotation == 270:
        image = image.transpose(Image.Transpose.ROTATE_270)

    image = ImageOps.pad(image, size, Image.Resampling.HAMMING, color="#ffffff")

    if dither:
        if bicolor:
            palette = [
            0, 0, 0,
            255, 0, 0,
            255, 255, 255
            ]

            p_img = Image.new('P', size)
            p_img.putpalette(palette * 64)
            conv = image.quantize(palette=p_img, dither=Image.Dither.FLOYDSTEINBERG)
            conv.save("test.png")

            img_data = conv.getdata()
            b = []
            r = []
            for item in img_data:
                if item == 0:
                    b.append(0)
                    r.append(1)
                elif item == 1:
                    b.append(1)
                    r.append(0)
                elif item == 2:
                    b.append(1)
                    r.append(1)
            image_b.putdata(b)
            image_r.putdata(r)
        else:
            image_b = image.convert('L',dither=Image.Dither.FLOYDSTEINBERG)
    else:
        image = image.convert('L')
        image_b = image.point(lambda p: p > threshold and 255)
        if invert and not bicolor:
            image_b = ImageOps.invert(image_b)

        if bicolor:
            print("Bicolor is on")
            image_r = image.point(lambda p: p > threshold + threshold_off and 255)
            image_r = ImageOps.invert(image_r)

    return image_b, image_r

# Image pusher

def push_image(pic, swap=False):
    image_b = pic[0]
    image_r = pic[1]

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

# Screen clearer

def clear_screen():
    epd.init()
    epd.Clear()
    epd.sleep()

# Text writer

def text_writer(text,size=defaults["text_size"],font_file=defaults["font_file"], pic="", location=defaults["location"]):

    if pic == "":
       image_b = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)
       image_r = Image.new('1', (epd4in2b.EPD_WIDTH, epd4in2b.EPD_HEIGHT), 255)
    else:
        image_b = pic[0]
        image_r = pic[1]

    drawblack = ImageDraw.Draw(image_b)
    font_data = ImageFont.truetype(font_file, size)
    drawblack.text( (location[0], location[1]), text, font = font_data, fill = 0)
    
    return image_b, image_r

# DisplayQueue handler

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
                if "dither" in job["options"]:
                    dither = True
                else:
                    dither = False             
                picture = convert_image(file=file,
                                    threshold=threshold,
                                    bicolor=bicolor,
                                    threshold_off=threshold_off,
                                    rotation=rotation,
                                    invert=invert,
                                    dither=dither)
                push_image(picture, swap)    
                print("Image displayed")

            elif job["type"] == "raw_display":
                print("Show raw image")
                raw_picture = job["raw_picture"]
                push_image(raw_picture)
                print("Image displayed")
            else:
                pass
        except:
          print('traceback.format_exc():\n%s', traceback.format_exc())
          continue
        time.sleep(5)

     
####
# Web-Interface
####

# Instanciate application
application = Flask(__name__)

# Add default route
@application.route('/')
def index():
    return render_template('index.html')

# Add loader routes
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
        if request.files[file].filename != '' and allowed_file(request.files[file].filename, config["ALLOWED_EXTENSIONS_PREPARED"]):
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


# Add converter routes
@application.route('/converter')
def converter():
    return render_template('converter.html')

@application.route('/converter', methods=['POST'])
def converterUpload():
    if 'file' not in request.files:
        print("No file in request")
        return 'No file in request',400
    file = request.files['file']
    if file.filename != '' and allowed_file(file.filename, config["ALLOWED_EXTENSIONS_GENERAL"]):
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

#Add clear route
@application.route('/clear')
def clear():
    job = {"type": "clear"}
    displayQueue.put(job)
    return redirect("/")


####
# Startup Sequence
####

# Queue Handler
threading.Thread(target=queue_handler).start()
time.sleep(2)

# Welcome Message
def welcome():
    text = "Startup Completed"
    pic = text_writer(text=text)
    hostname=socket.gethostname()   
    IPAddr=socket.gethostbyname(hostname)
    pic = text_writer(text="IP: " + IPAddr, location=[0,25], pic=pic)
    job = {"type":"raw_display", "raw_picture": pic}
    displayQueue.put(job)
#welcome()

# Web-Frontend
application.run(host=config["host"], port=config["port"])