import numpy as np
from PIL import Image
import cv2
import time
import matplotlib.pyplot as plt
import re
import pandas as pd
import sys
import os
templates = {}
templates_path = r'TextRecognition Templates'

for file in os.listdir(templates_path):
    if file.endswith('.png'):
        img = cv2.imread(os.path.join(templates_path, file), cv2.IMREAD_GRAYSCALE)
        templates[file[:-4]] = img
def find_text_by_template_matching(frame):
    text = ''
    for key in templates:
        template = templates[key]
        res = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)  # cv2.TM_CCORR_NORMED
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        print(f'{key} at {max_loc}')
        text += key + ', '
    return text

def use_setting_no_light(cap):
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)
    cap.set(cv2.CAP_PROP_BRIGHTNESS, -64)
    cap.set(cv2.CAP_PROP_CONTRAST, 64)
    cap.set(cv2.CAP_PROP_HUE, 40)
    cap.set(cv2.CAP_PROP_SATURATION, 128)
    cap.set(cv2.CAP_PROP_SHARPNESS, 3)
    cap.set(cv2.CAP_PROP_GAMMA, 72)
    cap.set(cv2.CAP_PROP_WHITE_BALANCE_RED_V, 4625)
    cap.set(cv2.CAP_PROP_BACKLIGHT, 0)
    cap.set(cv2.CAP_PROP_GAIN, 3)

def use_setting_light(cap):
    cap.set(cv2.CAP_PROP_EXPOSURE, -7)
    cap.set(cv2.CAP_PROP_BRIGHTNESS, -64)
    cap.set(cv2.CAP_PROP_CONTRAST, 64)
    cap.set(cv2.CAP_PROP_HUE, 40)
    cap.set(cv2.CAP_PROP_SATURATION, 128)
    cap.set(cv2.CAP_PROP_SHARPNESS, 3)
    cap.set(cv2.CAP_PROP_GAMMA, 72)
    cap.set(cv2.CAP_PROP_WHITE_BALANCE_RED_V, 4625)
    cap.set(cv2.CAP_PROP_BACKLIGHT, 0)
    cap.set(cv2.CAP_PROP_GAIN, 3)

# initialize camera
cap = cv2.VideoCapture(0,  cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

cap.set(cv2.CAP_PROP_SETTINGS, 1)

frame = np.zeros((1080, 1920))


plt.ion()
fig = plt.figure()
ax = fig.subplots()
imshow = ax.imshow(frame, cmap='gray')
ax.axis('off')
last_plot_time = pd.Timestamp.now()
plot_time_frequency = pd.Timedelta(0.5, 's')



# initialize file for saving data
start_time_str = pd.Timestamp.now().strftime('%Y-%m-%d-%H-%M-%S')
filename = f'{start_time_str}_Pressure.txt'
path = f'Data\Pressuredata\{filename}'

measuring_frequency = pd.Timedelta(10, 'min')
last_save_time = pd.Timestamp.now() - measuring_frequency
with open(path, 'w') as f:
    f.write('time,pressure\n')

values = []
mode = 'light'
#use_setting_light(cap)
while(True):
    try:
        time.sleep(1)
        ret, frame = cap.read()
        if mode == 'light':
            if np.sum(frame) < 85_000_000:
                print(f'Switching to no light mode {np.sum(frame)}')
                use_setting_no_light(cap)
                mode = 'no_light'
        elif mode == 'no_light':
            if np.sum(frame) > 100_000_000:
                print(f'Switching to light mode {np.sum(frame)}')
                use_setting_light(cap)
                mode = 'light'
        cv2.normalize(frame, frame, 0, 255, cv2.NORM_MINMAX)
        frame = np.flip(frame, axis=0)
        frame = np.flip(frame, axis=1)
        frame[:, :, 2] = 0  # remove blue part
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # go to gray scale

        frame = frame[280:500, 675:1150]  # cut out everything that is not the pressure reading

        text = find_text_by_template_matching(frame)

        pattern = r'\b\d\.\d+[E][-]?\d'
        if 'Pressure' in text:
            match = re.search(pattern, text)
            if match:
                value = match.group()
                values.append(float(value))

        now = pd.Timestamp.now()
        if now >= last_save_time + measuring_frequency:
            '''
            if len(values) > 0:
                value = np.median(values)
                with open(path, 'a+') as f:
                    f.write(str(now.strftime('%Y-%m-%d %H:%M:%S')))
                    f.write(',')
                    f.write(str(value))
                    f.write('\n')
                last_save_time = now
                values = []  # reset values
                print(now.strftime('%Y-%m-%d %H:%M:%S'), value)
            '''
            now_str = now.strftime('%Y-%m-%d-%H-%M-%S')
            last_save_time = now
            print(now_str, 'saving image')
            plt.imsave(f'Data\Pressuredata\RawImages\{now_str}.png', arr=frame, cmap='gray')

        if now >= last_plot_time + plot_time_frequency:
            imshow.set_data(frame)
            imshow.set_clim(vmin=frame.min(), vmax=frame.max())
            imshow.set_cmap('gray')
            ax.set_title(f'{text}')
            fig.canvas.draw()
            fig.canvas.flush_events()
            last_plot_time = pd.Timestamp.now()

    except KeyboardInterrupt:
        break
    except Exception as error:
        print(error)


cap.release()
cv2.destroyAllWindows()

'''
# Open the image file
image = Image.open('image.png')

# Perform OCR using PyTesseract
text = pytesseract.image_to_string(image)

# Print the extracted text
print(text)
'''