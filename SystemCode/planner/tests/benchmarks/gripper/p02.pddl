; IPC Gripper p02 — 4 balls, move all from room1 to room2
; Robot requires 2 round trips (2 grippers, 4 balls).
; Optimal plan length: 11
;   Trip 1 (5 steps): pick ball1+ball2, move, drop ball1+ball2
;   Return  (1 step):  move room2→room1
;   Trip 2 (5 steps): pick ball3+ball4, move, drop ball3+ball4
(define (problem gripper-p02)
  (:domain gripper)
  (:objects
    ball1 ball2 ball3 ball4 - ball
    room1 room2             - room
    lgripper rgripper       - gripper
  )
  (:init
    (at-robby room1)
    (at ball1 room1)
    (at ball2 room1)
    (at ball3 room1)
    (at ball4 room1)
    (free lgripper)
    (free rgripper)
  )
  (:goal (and
    (at ball1 room2)
    (at ball2 room2)
    (at ball3 room2)
    (at ball4 room2)
  ))
)
