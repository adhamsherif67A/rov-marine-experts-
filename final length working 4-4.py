import pyzed.sl as sl
import cv2
import math
import numpy as np
from datetime import datetime

# Initialize camera with GPU utilization
zed = sl.Camera()

# Initialize ZED camera parameters with GPU utilization enabled
init_params = sl.InitParameters(
    camera_resolution=sl.RESOLUTION.HD720,  # 720p resolution for higher FPS
    camera_fps=60,  # 60 FPS
    depth_mode=sl.DEPTH_MODE.ULTRA,  # Ultra depth mode for better precision
    coordinate_units=sl.UNIT.METER,  # Depth units in meters
    depth_maximum_distance=10,  # Maximum depth distance set to 10 meters
    depth_stabilization=1,  # Enable depth stabilization
    enable_image_enhancement=True,  # Image enhancement for better color accuracy
    sdk_gpu_id=0  # Specify GPU ID to use, defaults to 0 (first GPU)
)

# Open the ZED camera with the provided parameters
if zed.open(init_params) != sl.ERROR_CODE.SUCCESS:
    print("❌ Failed to open ZED 2i camera.")
    exit()

fps = zed.get_camera_information().camera_configuration.fps
print(f"✅ ZED 2i running at {fps} FPS")

# Enable positional tracking (uses GPU)
zed.enable_positional_tracking(sl.PositionalTrackingParameters())

runtime_parameters = sl.RuntimeParameters()
image_left = sl.Mat()
point_cloud = sl.Mat()

clicked_points = []
mouse_x, mouse_y = 0, 0
measured_distance = None
last_feedback = ""

def get_3d_point(event, x, y, flags, param):
    global clicked_points, mouse_x, mouse_y, measured_distance, last_feedback
    if event == cv2.EVENT_MOUSEMOVE:
        mouse_x, mouse_y = x, y
    elif event == cv2.EVENT_LBUTTONDOWN:
        err_code, point = point_cloud.get_value(x, y)
        if err_code == sl.ERROR_CODE.SUCCESS and len(point) >= 3:
            x3D, y3D, z3D = point[:3]
            if not any(map(lambda v: math.isnan(v) or math.isinf(v), (x3D, y3D, z3D))):
                clicked_points.append((x, y, x3D, y3D, z3D))
                last_feedback = f"✅ Point {len(clicked_points)} selected"
                print(f"Point ({x}, {y}): X={x3D:.3f}, Y={y3D:.3f}, Z={z3D:.3f} meters")

                if len(clicked_points) == 2:
                    p1, p2 = clicked_points
                    measured_distance = math.sqrt(
                        (p2[2] - p1[2])**2 +
                        (p2[3] - p1[3])**2 +
                        (p2[4] - p1[4])**2
                    ) * 100  # Convert to cm
                    last_feedback = f"📏 Distance: {measured_distance:.2f} cm"
                    print(last_feedback)
            else:
                last_feedback = "❌ Invalid depth data!"

cv2.namedWindow("ZED 2i Measurement")
cv2.setMouseCallback("ZED 2i Measurement", get_3d_point)

while True:
    if zed.grab(runtime_parameters) == sl.ERROR_CODE.SUCCESS:
        zed.retrieve_image(image_left, sl.VIEW.LEFT)
        zed.retrieve_measure(point_cloud, sl.MEASURE.XYZRGBA)
        img = np.copy(image_left.get_data())

        err_code, point = point_cloud.get_value(mouse_x, mouse_y)
        color = (0, 255, 0) if err_code == sl.ERROR_CODE.SUCCESS else (0, 0, 255)
        cv2.drawMarker(img, (mouse_x, mouse_y), color, cv2.MARKER_CROSS, 15, 2)

        for i, (u, v, _, _, _) in enumerate(clicked_points):
            clr = (0, 255, 0) if i == 0 else (0, 0, 255)
            cv2.circle(img, (u, v), 8, clr, -1)
            cv2.putText(img, f"P{i+1}", (u + 10, v - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, clr, 2)

        if len(clicked_points) == 2:
            pt1 = clicked_points[0][:2]
            pt2 = clicked_points[1][:2]
            cv2.line(img, pt1, pt2, (255, 255, 0), 2)

        cv2.putText(img, "Click 2 points to measure (in cm)", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        if measured_distance is not None:
            cv2.putText(img, f"Distance: {measured_distance:.2f} cm", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        if last_feedback:
            cv2.putText(img, last_feedback, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 200), 2)

        cv2.imshow("ZED 2i Measurement", img)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        print("👋 Exiting...")
        break
    elif key == ord('r'):
        clicked_points.clear()
        measured_distance = None
        last_feedback = "🔄 Reset!"
    elif key == ord('u'):
        if clicked_points:
            clicked_points.pop()
            measured_distance = None
            last_feedback = "↩️ Last point removed!"
    elif key == ord('s'):
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        cv2.imwrite(filename, img)
        last_feedback = f"📸 Screenshot saved as {filename}"

cv2.destroyAllWindows()
zed.close()
