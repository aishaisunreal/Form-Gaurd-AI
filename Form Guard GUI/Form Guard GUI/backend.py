import cv2
import mediapipe as mp
import numpy as np
import numpy.typing as npt
import re
import threading
import time
from enum import Enum
from collections import Counter

# from mediapipe.python.solutions import drawing_utils, pose
# mp_drawing = drawing_utils
# mp_pose = pose
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


def get_points(landmarks) -> dict[str, list[float]]:
    pts = {}
    for landmark in mp_pose.PoseLandmark:
        pts[landmark.name.lower()] = [
            landmarks[landmark.value].x,
            landmarks[landmark.value].y,
            landmarks[landmark.value].z
        ]
    return pts

def calculate_angle(a: list[float], b: list[float], c: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    angle = np.degrees(np.arccos(cosine_angle))
    return angle


def get_arrow(a: list[float], b: list[float], rotate_clockwise: bool) -> npt.NDArray[np.float64]:
    vec_x = b[0] - a[0]
    vec_y = b[1] - a[1]

    if rotate_clockwise:
        rotated_vec_x, rotated_vec_y = vec_y, -vec_x
    else:
        rotated_vec_x, rotated_vec_y = -vec_y, vec_x

    arrow = np.array([rotated_vec_x, rotated_vec_y])
    arrow = arrow / np.linalg.norm(arrow)
    return arrow

def draw_arrow(image: npt.NDArray, point: list[float], arrow: npt.NDArray, increase: bool):
    h, w, _ = image.shape
    point = np.array(point)
    arrow_magnitude = 50
    arrow = arrow_magnitude * arrow if increase else -arrow_magnitude * arrow

    x1, y1 = int(point[0] * w), int(point[1] * h)
    x2, y2 = int(x1 + arrow[0]), int(y1 + arrow[1])

    cv2.arrowedLine(image, (x1, y1), (x2, y2), color=(0, 0, 255), thickness=2)  


class RepStage(Enum):
    CONTRACTION = 1
    RELAXATION  = 2

class Workout(Enum):
    PUSHUPS        = 1
    BICEP_CURLS    = 2
    LATERAL_RAISES = 3
    OVERHEAD_PRESS = 4
    OVERHEAD_TRICEP_EXTENSION  = 5

def get_rep_stage(
    previous_rep_stage: RepStage, 
    left_val: float, 
    right_val: float, 
    relax_threshold: float,
    contract_threshold: float,
    reversed_threshold: bool
) -> RepStage:
    if reversed_threshold:
        if left_val > relax_threshold and right_val > relax_threshold:
            return RepStage.RELAXATION
        elif left_val < contract_threshold and right_val < contract_threshold:
            return RepStage.CONTRACTION
        else:
            return previous_rep_stage
    else:
        if left_val < relax_threshold and right_val < relax_threshold:
            return RepStage.RELAXATION
        elif left_val > contract_threshold and right_val > contract_threshold:
            return RepStage.CONTRACTION
        else:
            return previous_rep_stage


def check_pushup(angles, phase, image, points, arrows):
    ranges = {
        "elbow": (40, 150),
        "shoulder": (30, 60),
        "hip": (150, 180),
        "knee": (160, 180),
        "ankle": (50, 110)
    }
    results = {}
    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]
        knee = angles[f"{side}_knee"]
        ankle = angles[f"{side}_ankle"]

    
        elbow_ok = ranges["elbow"][0] <= elbow <= ranges["elbow"][1]
        shoulder_ok = ranges["shoulder"][0] <= shoulder <= ranges["shoulder"][1]
        hip_ok = ranges["hip"][0] <= hip <= ranges["hip"][1]
        knee_ok = ranges["knee"][0] <= knee <= ranges["knee"][1]
        ankle_ok = ranges["ankle"][0] <= ankle <= ranges["ankle"][1]
        results[side] = elbow_ok and shoulder_ok and hip_ok and knee_ok and ankle_ok
  
        
        # Feedback for Elbow
        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: relax more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], True)
        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: contract more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], False)

        # Shoulder feedback
        if shoulder < ranges["shoulder"][0]:
            errors.append(f"{side} shoulder: raise (now: {int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True)
        elif shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder: lower (now: {int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False)

        # Hip feedback
        if hip < ranges["hip"][0]:
            errors.append(f"{side} hip: lift (now: {int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
            draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], True)
        elif hip > ranges["hip"][1]:
            errors.append(f"{side} hip: lower (now: {int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
            draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], False)

        # Knee feedback
        if knee < ranges["knee"][0]:
            errors.append(f"{side} knee: straighten (now: {int(knee)}, target: {ranges['knee'][0]}-{ranges['knee'][1]})")
            draw_arrow(image, points[f"{side}_ankle"], arrows[f"{side}_knee"], True)
        elif knee > ranges["knee"][1]:
            errors.append(f"{side} knee: bend (now: {int(knee)}, target: {ranges['knee'][0]}-{ranges['knee'][1]})")
            draw_arrow(image, points[f"{side}_ankle"], arrows[f"{side}_knee"], False)

        # Ankle feedback
        if ankle < ranges["ankle"][0]:
            errors.append(f"{side} ankle: flex more (now: {int(ankle)}, target: {ranges['ankle'][0]}-{ranges['ankle'][1]})")
            draw_arrow(image, points[f"{side}_foot_index"], arrows[f"{side}_ankle"], True)
        elif ankle > ranges["ankle"][1]:
            errors.append(f"{side} ankle: relax more (now: {int(ankle)}, target: {ranges['ankle'][0]}-{ranges['ankle'][1]})")
            draw_arrow(image, points[f"{side}_foot_index"], arrows[f"{side}_ankle"], False)

    state = len(errors) == 0
    return state, errors

def check_bicep_curl(angles, phase, image, points, arrows):
    ranges = {
        "elbow": (40, 170),
        "shoulder": (0, 40),
        "hip": (160, 180)
    }

    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: relax more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], True)
        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: contract more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], False)

        if shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder: close your shoulders ({int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False)
      
        # if hip < ranges["hip"][0]:
        #     errors.append(f"{side} hip: lean more back ({int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
        #     draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], True)
        # elif hip > ranges["hip"][1]:
        #     errors.append(f"{side} hip: lean more forward ({int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
        #     draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], False)

    state = len(errors) == 0
    return state, errors

def check_lateral_raise(angles, phase, image, points, arrows):
    ranges = {
        "shoulder_down": (0, 30),
        "shoulder_up": (70, 110),
        "elbow": (150, 180),
        "hip": (150, 180)
    }

    results = {}
    errors = []

    for side in ["left", "right"]:
        shoulder = angles[f"{side}_shoulder"]
        elbow = angles[f"{side}_elbow"]
        hip = angles[f"{side}_hip"]

        shoulder_ok = (
            ranges["shoulder_down"][0] <= shoulder <= ranges["shoulder_down"][1]
            or
            ranges["shoulder_up"][0] <= shoulder <= ranges["shoulder_up"][1]
        )

        elbow_ok = ranges["elbow"][0] <= elbow <= ranges["elbow"][1]
        hip_ok = ranges["hip"][0] <= hip <= ranges["hip"][1]

        results[side] = shoulder_ok and elbow_ok and hip_ok

        if phase == "relaxation":
            if shoulder > ranges["shoulder_down"][1]:
                errors.append(f"{side} arm: lower your arm ({int(shoulder)})")
                draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False)

        elif phase == "contraction":
            if shoulder < ranges["shoulder_up"][0]:
                errors.append(f"{side} arm: raise higher ({int(shoulder)})")
                draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True)
            elif shoulder > ranges["shoulder_up"][1]:
                errors.append(f"{side} arm: too high ({int(shoulder)})")
                draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False)

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: don't bend too much ({int(elbow)})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], True)

        # if hip < ranges["hip"][0]:
        #     errors.append(f"{side} hip: leaning forward ({int(hip)})")
        #     draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], True)
        # elif hip > ranges["hip"][1]:
        #     errors.append(f"{side} hip: leaning back ({int(hip)})")
        #     draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], False)

    state = len(errors) == 0
    return state, errors

def check_overhead_press(angles, phase, image, points, arrows):
    ranges = {
        "elbow": (80, 180),
        "shoulder": (70, 180),
        "hip": (160, 180)
    }

    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow:  push your arms higher above your head({int(elbow)}°, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], True)

        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: don’t push too hard at the top ({int(elbow)}°, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], False)

        if shoulder < ranges["shoulder"][0]:
            errors.append(f"{side} shoulder:lift the weight higher ({int(shoulder)}°, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True)

        elif shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder:bring the weight down slowly ({int(shoulder)}°, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False)

    state = len(errors) == 0
    return state, errors

def check_overhead_tricep_extension(angles, phase, image, points, arrows):
    ranges = {
        "elbow": (50, 170),
        "shoulder": (110, 170),
        "hip": (150, 180)
    }

    errors = []

    for side in ["left", "right"]:
        elbow = angles[f"{side}_elbow"]
        shoulder = angles[f"{side}_shoulder"]
        hip = angles[f"{side}_hip"]

        if elbow < ranges["elbow"][0]:
            errors.append(f"{side} elbow: relax more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], True)
        elif elbow > ranges["elbow"][1]:
            errors.append(f"{side} elbow: contract more ({int(elbow)}, target: {ranges['elbow'][0]}-{ranges['elbow'][1]})")
            draw_arrow(image, points[f"{side}_wrist"], arrows[f"{side}_elbow"], False)

        if shoulder < ranges["shoulder"][0]:
            errors.append(f"{side} shoulder: open your shoulders ({int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], True)
        elif shoulder > ranges["shoulder"][1]:
            errors.append(f"{side} shoulder: close your shoulders ({int(shoulder)}, target: {ranges['shoulder'][0]}-{ranges['shoulder'][1]})")
            draw_arrow(image, points[f"{side}_elbow"], arrows[f"{side}_shoulder"], False)
      
        # if hip < ranges["hip"][0]:
        #     errors.append(f"{side} hip: lean more back ({int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
        #     draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], True)
        # elif hip > ranges["hip"][1]:
        #     errors.append(f"{side} hip: lean more forward ({int(hip)}, target: {ranges['hip'][0]}-{ranges['hip'][1]})")
        #     draw_arrow(image, points[f"{side}_hip"], arrows[f"{side}_hip"], False)

    state = len(errors) == 0
    return state, errors


class FormGuard:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 10000)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 10000)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.pose = mp_pose.Pose(model_complexity=2)

        self.check_func = {
            Workout.PUSHUPS:        check_pushup,
            Workout.BICEP_CURLS:    check_bicep_curl,
            Workout.LATERAL_RAISES: check_lateral_raise,
            Workout.OVERHEAD_PRESS: check_overhead_press,
            Workout.OVERHEAD_TRICEP_EXTENSION: check_overhead_tricep_extension,
        }

        self.is_running = True

        self.selected_workout = Workout.PUSHUPS
        self.reps = 0
        self.previous_rep_stage = RepStage.CONTRACTION

        self.frame: npt.NDArray = None
        self.text_status = ""
        
        self.error_log = [] 
        self.rep_timestamps = []
        self.workout_start_time = time.time()
        self.WORKOUT_DURATION = 30

    def reset(self):
        self.is_running = True
        self.reps = 0
        self.previous_rep_stage = RepStage.CONTRACTION
        self.error_log.clear()
        self.rep_timestamps.clear()
        self.workout_start_time = time.time()
    
    def update_workout(self, new_workout: Workout):
        if self.selected_workout != new_workout:
            self.reset()
        self.selected_workout = new_workout        
    
    def generate_summary(self):
        text_reps = f"Reps Completed: {self.reps}"

        if len(self.rep_timestamps) >= 2:
            elapsed = self.rep_timestamps[-1] - self.rep_timestamps[0]
            avg_speed = (len(self.rep_timestamps) - 1) / elapsed * 60
            text_speed = f"Average Speed: {avg_speed:.1f} reps/min"
        else:
            text_speed = "Average Speed: N/A"

        if self.error_log:
            most_common = Counter(self.error_log).most_common(1)[0][0]
            text_common_error = f"Most Common Error: {most_common}"
        else:
            text_common_error = "Most Common Error: None - great form!"

        return text_reps, text_speed, text_common_error

    def run(self):
        workouts_full_body = [Workout.PUSHUPS]
        workouts_upper_body = [Workout.BICEP_CURLS, Workout.LATERAL_RAISES, Workout.OVERHEAD_PRESS, Workout.OVERHEAD_TRICEP_EXTENSION]

        while self.cap.isOpened():
            if not self.is_running:
                continue

            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            text_status = ""

            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            mp_drawing.draw_landmarks(
                image,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2)
            )

            try:
                world_landmarks = results.pose_world_landmarks.landmark
                world_points = get_points(world_landmarks)
                if self.selected_workout in workouts_full_body: angles = {
                    "left_elbow": calculate_angle(world_points["left_shoulder"], world_points["left_elbow"], world_points["left_wrist"]),
                    "right_elbow": calculate_angle(world_points["right_shoulder"], world_points["right_elbow"], world_points["right_wrist"]),
                    "left_shoulder": calculate_angle(world_points["left_hip"], world_points["left_shoulder"], world_points["left_elbow"]),
                    "right_shoulder": calculate_angle(world_points["right_hip"], world_points["right_shoulder"], world_points["right_elbow"]),
                    "left_hip": calculate_angle(world_points["left_shoulder"], world_points["left_hip"], world_points["left_knee"]),
                    "right_hip": calculate_angle(world_points["right_shoulder"], world_points["right_hip"], world_points["right_knee"]),
                    "left_knee": calculate_angle(world_points["left_hip"], world_points["left_knee"], world_points["left_ankle"]),
                    "right_knee": calculate_angle(world_points["right_hip"], world_points["right_knee"], world_points["right_ankle"]),
                    "left_ankle": calculate_angle(world_points["left_knee"], world_points["left_ankle"], world_points["left_foot_index"]),
                    "right_ankle": calculate_angle(world_points["right_knee"], world_points["right_ankle"], world_points["right_foot_index"])
                }
                elif self.selected_workout in workouts_upper_body: angles = {
                    "left_elbow": calculate_angle( world_points["left_shoulder"],  world_points["left_elbow"],  world_points["left_wrist"]),
                    "right_elbow": calculate_angle( world_points["right_shoulder"],  world_points["right_elbow"],  world_points["right_wrist"]),
                    "left_shoulder": calculate_angle( world_points["left_hip"],  world_points["left_shoulder"],  world_points["left_elbow"]),
                    "right_shoulder": calculate_angle( world_points["right_hip"],  world_points["right_shoulder"],  world_points["right_elbow"]),
                    "left_hip": calculate_angle( world_points["left_shoulder"],  world_points["left_hip"],  world_points["left_knee"]),
                    "right_hip": calculate_angle( world_points["right_shoulder"],  world_points["right_hip"],  world_points["right_knee"])
                }

                landmarks = results.pose_landmarks.landmark
                points = get_points(landmarks)

                arrows = {
                    "left_elbow": get_arrow(points["left_elbow"], points["left_wrist"], rotate_clockwise=False),
                    "right_elbow": get_arrow(points["right_elbow"], points["right_wrist"], rotate_clockwise=True),
                    "left_shoulder": get_arrow(points["left_shoulder"], points["left_elbow"], rotate_clockwise=True),
                    "right_shoulder": get_arrow(points["right_shoulder"], points["right_elbow"], rotate_clockwise=False),
                    "left_hip": get_arrow(points["left_shoulder"], points["left_hip"], rotate_clockwise=True),
                    "right_hip": get_arrow(points["right_shoulder"], points["right_hip"], rotate_clockwise=False),
                    "left_knee": get_arrow(points["left_knee"], points["left_ankle"], rotate_clockwise=False),
                    "right_knee": get_arrow(points["right_knee"], points["right_ankle"], rotate_clockwise=True),
                    "left_ankle": get_arrow(points["left_ankle"], points["left_foot_index"], rotate_clockwise=True),
                    "right_ankle": get_arrow(points["right_ankle"], points["right_foot_index"], rotate_clockwise=False)
                }

                for joint_name, angle in angles.items():
                    h, w, _ = image.shape
                    coords = tuple(np.multiply(points[joint_name][:2], [w, h]).astype(int))
                    cv2.putText(image, str(int(angle)), coords, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5, cv2.LINE_AA)
                    cv2.putText(image, str(int(angle)), coords, cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

                phase = self.previous_rep_stage.name.lower()
                state, errors = self.check_func[self.selected_workout](angles, phase, image, points, arrows)

                if state:
                    text_status = "Good form!"
                else:
                    text_status = errors[0]

                if not state:
                    clean_errors = [re.sub(r'\s*\(.*?\)', '', e).strip() for e in errors]
                    self.error_log.extend(clean_errors)
                current_rep_stage = self.previous_rep_stage  
                if state:
                    if self.selected_workout == Workout.PUSHUPS: 
                        current_rep_stage = get_rep_stage(self.previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 80, 110, False)
                    elif self.selected_workout == Workout.BICEP_CURLS: 
                        current_rep_stage = get_rep_stage(self.previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 80, 140, False)
                    elif self.selected_workout == Workout.LATERAL_RAISES: 
                        current_rep_stage = get_rep_stage(self.previous_rep_stage, angles["left_shoulder"], angles["right_shoulder"], 70, 30, True)
                    elif self.selected_workout == Workout.OVERHEAD_PRESS: 
                        current_rep_stage = get_rep_stage(self.previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 110, 150, False)
                    elif self.selected_workout == Workout.OVERHEAD_TRICEP_EXTENSION: 
                        current_rep_stage = get_rep_stage(self.previous_rep_stage, angles["left_elbow"], angles["right_elbow"], 140, 100, True)
                    
                    if current_rep_stage != self.previous_rep_stage:
                        self.previous_rep_stage = current_rep_stage
                        if self.previous_rep_stage == RepStage.CONTRACTION:
                            self.reps += 1
                            self.rep_timestamps.append(time.time())

            except Exception as e:
                text_status = "No person detected!"

            elapsed = time.time() - self.workout_start_time
            time_remaining = max(0, self.WORKOUT_DURATION - elapsed)

            timer_color = (0, 0, 255) if time_remaining <= 10 else (255, 255, 255)  # turns red last 10 seconds
            timer_text = f"Time: {int(time_remaining)}s"
            cv2.putText(image, timer_text, (self.width - 250, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 5, cv2.LINE_AA)
            cv2.putText(image, timer_text, (self.width - 250, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, timer_color, 2, cv2.LINE_AA)

            self.frame = image
            self.text_status = text_status
        
        self.cap.release()
        self.pose.close()

# if __name__ == "__main__":
#     backend = FormGuard()
#     backend.run()
