import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
from pypylon import pylon
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import csv
import os
import time

class ImageSegmentationControl:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Segmentation Control")

        self.display_var = tk.StringVar(value="both")
        self.camera = None
        self.line_counts = []
        self.blob_counts = []
        self.image_data = []

        self.initialize_gui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_camera()

    def initialize_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(sticky=(tk.W, tk.E, tk.N, tk.S))

        self.video_label = ttk.Label(main_frame)
        self.video_label.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.start_video_button = ttk.Button(main_frame, text="Start Video Feed", command=self.start_video_feed)
        self.start_video_button.grid(row=1, column=0, pady=10, sticky=tk.W)

        self.stop_video_button = ttk.Button(main_frame, text="Stop Video Feed", command=self.stop_video_feed)
        self.stop_video_button.grid(row=1, column=1, pady=10, sticky=tk.W)

        radio_button_frame = ttk.LabelFrame(main_frame, text="Display Options", padding=(10, 5))
        radio_button_frame.grid(row=2, column=0, columnspan=2, pady=10, padx=10, sticky=tk.W)

        options = ["lines", "blobs", "color", "edges", "contours", "shapes", "both"]
        for idx, option in enumerate(options):
            ttk.Radiobutton(radio_button_frame, text=option.capitalize(), variable=self.display_var, value=option).grid(row=idx, column=0, sticky=tk.W, pady=2)

        self.fig, self.ax = plt.subplots(2, 1, figsize=(5, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=2, rowspan=7, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.save_button = ttk.Button(main_frame, text="Save Data", command=self.save_data)
        self.save_button.grid(row=3, column=0, columnspan=2, pady=10, sticky=tk.W)

    def setup_camera(self):
        self.release_camera()
        try:
            self.camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
            self.camera.Open()
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.blob_detector = self.setup_blob_detector()
        except Exception as e:
            print(f"Error setting up camera: {e}")

    def release_camera(self):
        if self.camera is not None:
            if self.camera.IsGrabbing():
                self.camera.StopGrabbing()
            self.camera.Close()
            self.camera = None

    def setup_blob_detector(self):
        params = cv2.SimpleBlobDetector_Params()
        params.filterByArea = True
        params.minArea = 150
        params.filterByCircularity = True
        params.minCircularity = 0.1
        params.filterByConvexity = True
        params.minConvexity = 0.5
        params.filterByInertia = True
        params.minInertiaRatio = 0.01
        return cv2.SimpleBlobDetector_create(params)

    def start_video_feed(self):
        if self.camera and not self.camera.IsGrabbing():
            try:
                self.camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
                self.update_camera_feed()
                print("Video feed started.")
            except Exception as e:
                print(f"Failed to start video feed: {e}")

    def stop_video_feed(self):
        if self.camera and self.camera.IsGrabbing():
            self.camera.StopGrabbing()
            print("Video feed stopped.")

    def update_camera_feed(self):
        if self.camera and self.camera.IsGrabbing() and self.root.winfo_exists():
            try:
                grabResult = self.camera.RetrieveResult(500, pylon.TimeoutHandling_ThrowException)
                if grabResult.GrabSucceeded():
                    image = self.converter.Convert(grabResult).GetArray()
                    self.process_image(image)
                grabResult.Release()
                if self.root.winfo_exists():
                    self.root.after(10, self.update_camera_feed)
            except Exception as e:
                print(f"Error during camera feed update: {e}")

    def process_image(self, image):
        display_image = image
        timestamp = time.time()
        line_count = 0
        blob_count = 0

        if self.display_var.get() == "lines":
            display_image, line_count = self.detect_lines(image)
        elif self.display_var.get() == "blobs":
            display_image, blob_count = self.detect_blobs(image)
        elif self.display_var.get() == "color":
            display_image = self.color_segmentation(image)
        elif self.display_var.get() == "edges":
            display_image = self.edge_detection(image)
        elif self.display_var.get() == "contours":
            display_image = self.contour_detection(image)
        elif self.display_var.get() == "shapes":
            display_image = self.shape_detection(image)
        else:
            line_image, line_count = self.detect_lines(image)
            blob_image, blob_count = self.detect_blobs(image)
            display_image = cv2.addWeighted(line_image, 0.5, blob_image, 0.5, 0)
            self.line_counts.append(line_count)
            self.blob_counts.append(blob_count)

        self.image_data.append([timestamp, line_count, blob_count])

        display_image = self.resize_image(display_image, 770, 400)
        self.update_image(self.video_label, display_image)
        self.update_graphs()

    def save_data(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if file_path:
            with open(file_path, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Timestamp", "Line Count", "Blob Count"])
                writer.writerows(self.image_data)
            print(f"Data saved to {file_path}")

    def update_image(self, label, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(image)
        image = ImageTk.PhotoImage(image)
        label.config(image=image)
        label.image = image

    def update_graphs(self):
        self.ax[0].clear()
        self.ax[0].plot(self.line_counts, 'r-')
        self.ax[0].set_title('Line Detection Count')
        self.ax[1].clear()
        self.ax[1].plot(self.blob_counts, 'b-')
        self.ax[1].set_title('Blob Detection Count')
        self.canvas.draw()
        self.canvas.flush_events()

    def detect_lines(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred_gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred_gray, 100, 200, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 50, minLineLength=50, maxLineGap=20)
        line_image = image.copy()
        line_count = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(line_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
                line_count += 1
        return line_image, line_count

    def detect_blobs(self, image):
        keypoints = self.blob_detector.detect(image)
        blob_image = cv2.drawKeypoints(image, keypoints, None, (0, 0, 255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
        return blob_image, len(keypoints)

    def color_segmentation(self, image):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_bound = np.array([0, 120, 70])
        upper_bound = np.array([180, 255, 255])
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        segmented_image = cv2.bitwise_and(image, image, mask=mask)
        return segmented_image

    def edge_detection(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_image = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        return edge_image

    def contour_detection(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour_image = image.copy()
        cv2.drawContours(contour_image, contours, -1, (0, 255, 0), 2)
        return contour_image

    def shape_detection(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        shape_image = image.copy()
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
            shape = self.identify_shape(approx)
            cv2.drawContours(shape_image, [approx], -1, (0, 255, 0), 2)
            x, y = approx[0][0]
            cv2.putText(shape_image, shape, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
        return shape_image

    def identify_shape(self, approx):
        num_sides = len(approx)
        if num_sides == 3:
            return "Triangle"
        elif num_sides == 4:
            (x, y, w, h) = cv2.boundingRect(approx)
            ar = w / float(h)
            return "Square" if 0.95 <= ar <= 1.05 else "Rectangle"
        elif num_sides == 5:
            return "Pentagon"
        else:
            return "Circle"

    def resize_image(self, image, width, height):
        return cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)

    def on_closing(self):
        self.release_camera()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageSegmentationControl(root)
    root.mainloop()
