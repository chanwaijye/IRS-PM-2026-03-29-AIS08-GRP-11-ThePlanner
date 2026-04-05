; IPC Gripper p01 — 2 balls, move all from room1 to room2
; Robot starts in room1 with both grippers free.
; Optimal plan length: 5
;   1. pick(ball1,room1,lgripper)
;   2. pick(ball2,room1,rgripper)
;   3. move(room1,room2)
;   4. drop(ball1,room2,lgripper)
;   5. drop(ball2,room2,rgripper)
(define (problem gripper-p01)
  (:domain gripper)
  (:objects
    ball1 ball2       - ball
    room1 room2       - room
    lgripper rgripper - gripper
  )
  (:init
    (at-robby room1)
    (at ball1 room1)
    (at ball2 room1)
    (free lgripper)
    (free rgripper)
  )
  (:goal (and
    (at ball1 room2)
    (at ball2 room2)
  ))
)
