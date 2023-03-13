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
            "display_model": "epd5in65f"}

# Display adjustment

if config["display_model"] == "epd4in2b":
    from waveshare_epd import epd4in2b_V2 as epd_lib
    config["display_type"] = "rbw"
elif config["display_model"] == "epd5in65f":
    from waveshare_epd import epd5in65f as epd_lib
    config["display_type"] = "acep"
else:
    print("Unknown display type")


# Objects

epd = epd_lib.EPD()
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

# DisplayQueue handler

def queue_handler():
    while True:
        try:
            job = displayQueue.get()
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

# Add image display routes
@application.route('/display')
def converter():
    return render_template('display.html')

@application.route('/display', methods=['POST'])
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
        job["type"] = "display"
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

# prepare folders
if not os.path.exists('images'):
   os.makedirs('images')

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
welcome()

# Web-Frontend
application.run(host=config["host"], port=config["port"])
