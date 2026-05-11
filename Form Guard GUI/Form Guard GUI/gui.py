from __future__ import annotations

import backend
import base64
import cv2
import numpy as np
import numpy.typing as npt
import threading
import time

from backend import FormGuard
from html_head_style import html_head_style
from nicegui import ui, app

ui.add_head_html(html_head_style)

class State:
    def __init__(self) -> State:
        self.panels = ["Workout Selection", "Workout Summary"]
        self.panel_selected = self.panels[0]

        self.workouts = { workout.name.replace("_", " ").title(): workout for workout in backend.Workout }
        self.workout_selected = list(self.workouts.keys())[0]
        
        self.frame: str = None
        self.rep_count = 0
        self.rep_stage = backend.RepStage.CONTRACTION
        self.text_status = ""
        self.workout_over = False
    
    def reset(self):
        self.frame = None
        self.rep_count = 0
        self.rep_stage = backend.RepStage.CONTRACTION
        self.text_status = ""
        self.workout_over = False

class GUI:
    def __init__(self):
        self.state = State()
        self.backend = FormGuard()
        threading.Thread(target=self.backend.run, daemon=True).start()

        with ui.page_sticky(position='top-right', x_offset=20, y_offset=20):
            self.exit_button = ui.button('x', on_click=app.shutdown).classes('exit-btn')
        
        with ui.page_sticky(position='top', y_offset=50).classes('justify-center items-center'):
            self.radio_panel_selection = ui.radio(self.state.panels, value=self.state.panel_selected,
                                                   on_change=self.panel_switch).bind_value(self.state, "panel_selected").classes('btn-radios')

        self.panel_main = ui.column().classes('w-full h-screen justify-center items-center gap-12')

        self.panel_switch()
            
    @staticmethod
    def frame_to_base64(frame: npt.NDArray, quality: int = 70) -> str:
        ret, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ret:
            return None
        return 'data:image/jpeg;base64,' + base64.b64encode(buf).decode('ascii')
    
    def update_state(self):
        if not self.backend.is_running:
            return

        if self.label_rep_count is not None:
            self.state.rep_count = self.backend.reps
            self.label_rep_count.text = f"Rep Count: {self.state.rep_count}"

        if self.label_rep_stage is not None:
            self.state.rep_stage = self.backend.previous_rep_stage
            self.label_rep_stage.text = f"Rep Stage: {self.state.rep_stage.name.title()}"

        if self.label_feedback is not None:
            self.state.text_status = self.backend.text_status
            if self.state.text_status == "Good form!":
                self.label_feedback.classes(remove="success error", add="success")
            else:
                self.label_feedback.classes(remove="success error", add="error")
            self.label_feedback.text = self.state.text_status

        if self.webcam is not None and self.backend.frame is not None:
            self.state.frame = self.frame_to_base64(self.backend.frame)
            self.webcam.source = self.state.frame
            self.webcam.update()
        
        if not self.state.workout_over and time.time() - self.backend.workout_start_time > self.backend.WORKOUT_DURATION:
            self.state.panel_selected = "Workout Summary"
            self.state.workout_over = True
            self.backend.is_running = False
    
    def update_workout(self):
        self.backend.update_workout(self.state.workouts[self.state.workout_selected])

    def panel_switch(self):
        self.panel_main.clear()
        self.state.reset()
        
        if self.state.panel_selected == "Workout Selection":
            self.show_workout_selection()
        elif self.state.panel_selected == "Workout Summary":
            self.show_workout_summary()
    
    def show_workout_selection(self):
        self.backend.reset()

        with self.panel_main:
            with ui.row().classes('justify-center items-center gap-12'):
                with ui.column().classes('justify-center items-center gap-8 w-[20vw] shrink-0').classes('container-style'):
                    self.cmb_workouts = ui.select(options=list(self.state.workouts.keys()), label="Workout", with_input=True,
                                            on_change=self.update_workout).bind_value(self.state, "workout_selected").classes('light-btn')
                    self.label_rep_count = ui.label("Rep Count").classes('custom-label').classes(add='custom-label-large-text')
                    self.label_rep_stage = ui.label("Rep Stage").classes('custom-label').classes(add='custom-label-large-text')
                
                self.placeholder_image = ("data:image/png;base64,"
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAA"
                            "AC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII=")
                
                self.webcam = ui.interactive_image(self.placeholder_image).classes('w-[60vw] object-cover'
                    ).style('box-shadow: 0 0 30px 6px rgba(59,130,246,0.6); border: 4px solid #111827;')

            self.label_feedback = ui.label("").classes('custom-label').classes(add='custom-label-large-text')

    def show_workout_summary(self):
        text_reps, text_speed, text_common_error = self.backend.generate_summary()
        
        with self.panel_main:
            with ui.column().classes('justify-center items-center gap-12').classes('container-style'):
                self.label_sum_reps = ui.label(text_reps).classes('custom-label').classes(add='custom-label-large-text')
                self.label_sum_speed = ui.label(text_speed).classes('custom-label').classes(add='custom-label-large-text')
                self.label_sum_error = ui.label(text_common_error).classes('custom-label').classes(add='custom-label-large-text')

if __name__ == "__main__":
    gui = GUI()
    ui.timer(0.01, gui.update_state)
    ui.run(reload=False, fullscreen=True)
