; IPC-1998 Gripper domain (typed STRIPS)
; A robot with two grippers moves balls between two rooms.
; Reference: IPC-1 benchmark set (Korf 1987 reused in IPC-1998).
(define (domain gripper)
  (:requirements :strips :typing :negative-preconditions)

  (:types ball room gripper)

  (:predicates
    (at-robby ?r - room)               ; robot is in room r
    (at       ?b - ball  ?r - room)    ; ball b is in room r
    (free     ?g - gripper)            ; gripper g is empty
    (carry    ?b - ball  ?g - gripper) ; gripper g holds ball b
  )

  ; move robot between rooms
  (:action move
    :parameters (?from - room ?to - room)
    :precondition (and
      (at-robby ?from)
    )
    :effect (and
      (at-robby ?to)
      (not (at-robby ?from))
    )
  )

  ; pick a ball from the current room using a free gripper
  (:action pick
    :parameters (?ball - ball ?room - room ?grip - gripper)
    :precondition (and
      (at-robby ?room)
      (at ?ball ?room)
      (free ?grip)
    )
    :effect (and
      (carry ?ball ?grip)
      (not (at ?ball ?room))
      (not (free ?grip))
    )
  )

  ; drop a carried ball in the current room
  (:action drop
    :parameters (?ball - ball ?room - room ?grip - gripper)
    :precondition (and
      (carry ?ball ?grip)
      (at-robby ?room)
    )
    :effect (and
      (at ?ball ?room)
      (free ?grip)
      (not (carry ?ball ?grip))
    )
  )
)
