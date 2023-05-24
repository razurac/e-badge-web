#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from flask import Flask, render_template, redirect, request, Response, url_for
from PIL import Image, ImageDraw, ImageFont, ImageOps
import sys
import os
from pprint import pprint
from picamera2 import Picamera2
from libcamera import Transform
import time
from datetime import datetime
import threading
import traceback
import queue
import socket
import uuid
import random

####
#  Setup
####

# Vars

defaults = {"location": [0,0],
            "font_file": "font/open-sans/bold.ttf",
            "text_size": 20}

config =   {"host": "0.0.0.0",
            "port": 8080,
            "ALLOWED_EXTENSIONS_GENERAL": set(['png', 'jpg', 'jpeg', 'webp', 'bmp']),
            "display_model": "epd5in65f",
            "slideshow_timer": 10}

# Display adjustment

if config["display_model"] == "epd4in2b":
    from waveshare_epd import epd4in2b_V2 as epd_lib
    config["display_type"] = "rbw"
elif config["display_model"] == "epd5in65f":
    from waveshare_epd import epd5in65f as epd_lib
    config["display_type"] = "acep"
else:
    print("Unknown display type")


# Init EPD
epd = epd_lib.EPD()

# Queues
displayQueue = queue.Queue()

# Events
slideshowEnabled = threading.Event()
displayActive = threading.Event()


# Multi Thread Lists
imageList = []


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
# Get own IP
def get_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('10.254.254.254', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

####
# Basic image functionality
####

# Converter for Images

def convert_image(file="", image="",  rotation=0, bw=False):

    if file != "":
        image = Image.open(file)
    elif image != "":
        pass
    else:
        print("Converter didn't get any valid image")
        return


    image = image.convert('RGB',dither=Image.Dither.NONE)
    size = (epd_lib.EPD_WIDTH, epd_lib.EPD_HEIGHT)
    if rotation == 90:
        image = image.transpose(Image.Transpose.ROTATE_90)
    elif rotation == 180:
        image = image.transpose(Image.Transpose.ROTATE_180)
    elif rotation == 270:
        image = image.transpose(Image.Transpose.ROTATE_270)

    image = ImageOps.pad(image, size, Image.Resampling.HAMMING, color="#000000")

    if config["display_type"] == "rbw":
        image_b = Image.new('1', (epd_lib.EPD_WIDTH, epd_lib.EPD_HEIGHT), 255)
        image_r = Image.new('1', (epd_lib.EPD_WIDTH, epd_lib.EPD_HEIGHT), 255)
        if not bw:
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
        return image_b, image_r
    elif config["display_type"] == "acep":
        if bw:
            image = image.convert('L')
        return image


# Image pusher

def push_image(image, swap=False):

    if config["display_type"] == "rbw":
        image_b = image[0]
        image_r = image[1]
    
    
        if swap:
            image_b, image_r = image_r, image_b
        try:
            epd.init()
            epd.send_command(0x50)
            epd.send_data(0x37)
            epd.display(epd.getbuffer(image_b), epd.getbuffer(image_r))
            epd.sleep()
        except:
            print('traceback.format_exc():\n%s', traceback.format_exc())
            epd.sleep()
            exit()
    elif config["display_type"] == "acep":
        epd.init()
        epd.send_command(0x50)
        epd.send_data(0x17)
        epd.display(epd.getbuffer(image))
        epd.sleep()


# Screen clearer

def clear_screen():
    epd.init()
    epd.Clear()
    epd.sleep()

# Text writer

def text_writer(text,size=defaults["text_size"],font_file=defaults["font_file"], image="", location=defaults["location"]):

    if image == "":
       image = Image.new('1', (epd_lib.EPD_WIDTH, epd_lib.EPD_HEIGHT), 255)

    draw = ImageDraw.Draw(image)
    font_data = ImageFont.truetype(font_file, size)
    draw.text( (location[0], location[1]), text, font = font_data, fill = 0)
    
    return image

# Slideshow handler

def slideshow_handler():
    while True:
        slideshowEnabled.wait()
        for filename in imageList:
            if not slideshowEnabled.is_set():
                break
            print("Next Slideshow Image" + filename)
            job = {}
            job["file"] = os.path.join("tmp_images/", filename)
            job["options"] = {"rotation": 0}
            job["type"] = "display"
            displayQueue.put(job)
            time.sleep(2)            
            while displayActive.is_set() or not displayQueue.empty():
                pass
            time.sleep(config["slideshow_timer"])




# DisplayQueue handler

def queue_handler():
    while True:
        try:
            job = displayQueue.get()
            displayActive.set()
            if job["type"] == "clear":
                print("Clear Screen")

                clear_screen()

                print("Screen cleared")
            elif job["type"] == "display":
                print("Display image")
                file = job["file"]
                rotation = int(job["options"]["rotation"])
                if "bw" in job["options"]:
                    bw = True
                else:
                    bw = False
             
                picture = convert_image(file=file,
                                    bw=bw,
                                    rotation=rotation,
                                    )
                push_image(picture)    
                print("Image displayed")

            elif job["type"] == "raw_display":
                print("Show raw image")
                raw_picture = job["raw_picture"]
                converted_pic = convert_image(image=raw_picture)
                push_image(converted_pic)
                print("Image displayed")
            else:
                pass
        except:
          print('traceback.format_exc():\n%s', traceback.format_exc())
          continue
        displayActive.clear()

     
####
# Web-Interface
####

# Instanciate application
application = Flask(__name__)

# Add default route
@application.route('/')
def index():
    return render_template('index.html')

# Add image display routes
@application.route('/display')
def converter():
    return render_template('display.html')

@application.route('/display', methods=['POST'])
def converterUpload():
    slideshowEnabled.clear()
    if 'file' not in request.files:
        print("No file in request")
        return 'No file in request',400
    file = request.files['file']
    if file.filename != '' and allowed_file(file.filename, config["ALLOWED_EXTENSIONS_GENERAL"]):
        file.save(os.path.join("tmp_images/", file.filename))
        job = {}
        job["file"] = os.path.join("tmp_images/", file.filename)
        job["options"] = request.form
        job["type"] = "display"
        displayQueue.put(job)
        return redirect(request.url)
    else:
        print("No file selected or invalid file type")
        return 'No file selected or invalid file type',400


# Add photo routes
@application.route('/camera')
def camera():
    return render_template('camera.html')

@application.route('/camera', methods=['POST'])
def cameraTakePic():
    try:
        slideshowEnabled.clear()
        now = datetime.now()
        date_time = now.strftime("%m-%d-%Y")
        filename = date_time + "-" + uuid.uuid4().hex[:5] + ".png"
        picam2.capture_file(os.path.join("tmp_images/", filename))
        job = {}
        job["file"] = os.path.join("tmp_images/", filename)
        job["options"] = {"rotation": 0}
        job["type"] = "display"
        displayQueue.put(job)
        return redirect(request.url)
    except:
        print("Error when taking picture")
        return 'Error when taking picture',500

@application.route('/slideshow')
def slideshowMainPage():
    return render_template('slideshow.html')

@application.route('/slideshow', methods=['POST'])
def slideshowToggle():
    try:
        if not slideshowEnabled.is_set():
            print("Enable slideshow")
            displayQueue.queue.clear
            dir_path = r'slideshow'
            for file in os.listdir(dir_path):
                if os.path.isfile(os.path.join(dir_path, file)) and allowed_file(file, config["ALLOWED_EXTENSIONS_GENERAL"]):
                    imageList.append(os.path.abspath(os.path.join(dir_path, file)))
                    random.shuffle(imageList)
            slideshowEnabled.set()
        else:
            print("Disable slideshow")
            slideshowEnabled.clear()
        return redirect(request.url)
    except:
        print("Error when toggle slideshow")
        return 'Error when toggle slideshow',500





#Add clear route
@application.route('/clear')
def clear():
    slideshowEnabled.clear()
    job = {"type": "clear"}
    displayQueue.put(job)
    return redirect("/")


####
# Startup Sequence
####

# prepare folders
if not os.path.exists('tmp_images'):
   os.makedirs('tmp_images')

if not os.path.exists('slideshow'):
   os.makedirs('slideshow')

# Init picamera

try:
    picam2 = Picamera2()
    camera_config = picam2.create_preview_configuration(transform=Transform(hflip=True, vflip=True))
    picam2.configure(camera_config)
    picam2.start(show_preview=False)
except:
    pass

# Slideshow Handler
threading.Thread(target=slideshow_handler).start()
time.sleep(2)

# Queue Handler
threading.Thread(target=queue_handler).start()
time.sleep(2)

# Welcome Message
def welcome():
    text = "Startup Completed"
    image = text_writer(text=text)
    image = text_writer(text="Open Web-UI: " + get_ip()+":"+str(config["port"]), location=[0,25], image=image)
    job = {"type":"raw_display", "raw_picture": image}
    displayQueue.put(job)
# welcome()

# Web-Frontend
application.run(host=config["host"], port=config["port"])
