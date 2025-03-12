import cv2
import os
import sys
import numpy as np
import glob
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget
from PyQt5.QtCore import Qt
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
from PIL import Image



def ensure_directory_exists(directory):
    """Ensure the specified directory exists, or create it."""
    if not os.path.exists(directory):
        os.makedirs(directory)


def capture_images():
    """Capture images from the camera and save them to the 'images' directory."""
    images_dir = "images"
    ensure_directory_exists(images_dir)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not access the camera.")
        return False

    print("Press 'c' to capture a photo, or 'q' to quit.")
    photo_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to capture image.")
            break

        cv2.imshow("Camera", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('c'):  # Press 'c' to capture a photo
            photo_count += 1
            photo_path = os.path.join(images_dir, f"photo_{photo_count}.jpg")
            cv2.imwrite(photo_path, frame)
            print(f"Photo saved: {photo_path}")
        elif key == ord('q'):  # Press 'q' to quit
            break

    cap.release()
    cv2.destroyAllWindows()
    return True


def create_panorama():
    """Create a panorama image from the captured images."""
    image_paths = sorted(glob.glob("images/*.jpg"))
    images = [cv2.imread(img) for img in image_paths]

    if any(img is None for img in images):
        print("Error: Some images failed to load.")
        return None

    stitcher = cv2.Stitcher_create(cv2.Stitcher_PANORAMA)
    (status, panorama) = stitcher.stitch(images)

    if status == cv2.Stitcher_OK:
        panorama_path = "panorama.jpg"
        cv2.imwrite(panorama_path, panorama)
        print(f"✅ Panorama created successfully! Saved to {panorama_path}")
        return panorama_path
    else:
        print("Failed to create panorama. Check image overlap and quality.")
        return None


class PanoramaViewer(QOpenGLWidget):
    def _init_(self, image_path, parent=None):
        super()._init_(parent)
        self.image_path = image_path
        self.texture_id = None
        self.last_x, self.last_y = 0, 0
        self.yaw, self.pitch, self.roll = 0, 0, 0
        self.mouse_button_pressed = None

    def initializeGL(self):
        glEnable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0, 0, 0, 1)
        self.texture_id = self.loadTexture(self.image_path)

    def resizeGL(self, width, height):
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(90, width / height, 0.1, 100)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glRotatef(-self.pitch, 1, 0, 0)
       # glRotatef(-self.yaw, 0, 1, 0)
        glRotatef(-self.yaw, 0, 0, 1)
        self.drawSphere()

    def drawSphere(self):
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        quadric = gluNewQuadric()
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricOrientation(quadric, GLU_INSIDE)
        gluSphere(quadric, 5, 50, 50)

    def loadTexture(self, image_path):
        img = Image.open(image_path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img_data = np.array(img, dtype=np.uint8)

        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, img_data)

        return texture_id

    def mousePressEvent(self, event):
        self.last_x, self.last_y = event.x(), event.y()
        self.mouse_button_pressed = event.button()

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_x
        dy = event.y() - self.last_y
        self.last_x, self.last_y = event.x(), event.y()

        if self.mouse_button_pressed == Qt.LeftButton:
            self.yaw -= dx * 0.2
            self.pitch += dy * 0.2
        elif self.mouse_button_pressed == Qt.RightButton:
            self.roll += dx * 0.2
        self.update()

    def mouseReleaseEvent(self, event):
        self.mouse_button_pressed = None


class MainWindow(QMainWindow):
    def _init_(self, image_path):
        super()._init_()
        self.setWindowTitle("360° Panorama Viewer")
        self.viewer = PanoramaViewer(image_path)
        self.setCentralWidget(self.viewer)
        self.resize(800, 600)


if __name__ == "_main_":
    if capture_images():
        panorama_path = create_panorama()
        if panorama_path:
            app = QApplication(sys.argv)
            window = MainWindow(panorama_path)
            window.show()
            sys.exit(app.exec_())