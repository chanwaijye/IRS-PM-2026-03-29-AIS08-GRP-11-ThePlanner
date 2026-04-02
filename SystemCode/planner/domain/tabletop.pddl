(define (domain tabletop)
  (:requirements :strips :typing :negative-preconditions)

  (:types
    robot object location - object
  )

  (:predicates
    (on ?obj - object ?loc - location)          ; obj rests on a location/surface
    (on_table ?obj - object)                    ; obj is directly on the table
    (clear ?obj - object)                       ; nothing is on top of obj
    (holding ?robot - robot ?obj - object)      ; robot is holding obj
    (hand_empty ?robot - robot)                 ; robot gripper is free
    (at ?robot - robot ?loc - location)         ; robot is at location
    (heavy ?obj - object)                       ; obj weighs > 0.5 kg (two-hand protocol)
    (fragile ?obj - object)                     ; obj requires careful handling
    (in_zone ?obj - object ?loc - location)     ; obj is within a named zone
    (stacked_on ?obj_top - object ?obj_bottom - object) ; obj_top is on obj_bottom
  )

  ; -----------------------------------------------------------------------
  ; move_to: navigate robot base between locations
  ; -----------------------------------------------------------------------
  (:action move_to
    :parameters (?robot - robot ?from - location ?to - location)
    :precondition (and
      (at ?robot ?from)
    )
    :effect (and
      (not (at ?robot ?from))
      (at ?robot ?to)
    )
  )

  ; -----------------------------------------------------------------------
  ; pick: lift an object from a surface location
  ; -----------------------------------------------------------------------
  (:action pick
    :parameters (?robot - robot ?obj - object ?from_loc - location)
    :precondition (and
      (at ?robot ?from_loc)
      (on ?obj ?from_loc)
      (clear ?obj)
      (hand_empty ?robot)
      (not (heavy ?obj))          ; heavy objects require explicit two-hand pick
    )
    :effect (and
      (holding ?robot ?obj)
      (not (hand_empty ?robot))
      (not (on ?obj ?from_loc))
      (not (on_table ?obj))
    )
  )

  ; -----------------------------------------------------------------------
  ; place: set a held object down on a surface location
  ; -----------------------------------------------------------------------
  (:action place
    :parameters (?robot - robot ?obj - object ?to_loc - location)
    :precondition (and
      (at ?robot ?to_loc)
      (holding ?robot ?obj)
    )
    :effect (and
      (on ?obj ?to_loc)
      (on_table ?obj)
      (clear ?obj)
      (hand_empty ?robot)
      (not (holding ?robot ?obj))
      (in_zone ?obj ?to_loc)
    )
  )

  ; -----------------------------------------------------------------------
  ; stack: place held object on top of another object
  ; -----------------------------------------------------------------------
  (:action stack
    :parameters (?robot - robot ?obj_top - object ?obj_bottom - object ?loc - location)
    :precondition (and
      (at ?robot ?loc)
      (holding ?robot ?obj_top)
      (on ?obj_bottom ?loc)
      (clear ?obj_bottom)
      (not (fragile ?obj_bottom))
    )
    :effect (and
      (stacked_on ?obj_top ?obj_bottom)
      (on ?obj_top ?loc)
      (not (clear ?obj_bottom))
      (clear ?obj_top)
      (hand_empty ?robot)
      (not (holding ?robot ?obj_top))
    )
  )

  ; -----------------------------------------------------------------------
  ; unstack: remove top object from a stack
  ; -----------------------------------------------------------------------
  (:action unstack
    :parameters (?robot - robot ?obj_top - object ?obj_bottom - object ?loc - location)
    :precondition (and
      (at ?robot ?loc)
      (hand_empty ?robot)
      (stacked_on ?obj_top ?obj_bottom)
      (on ?obj_top ?loc)
      (clear ?obj_top)
    )
    :effect (and
      (holding ?robot ?obj_top)
      (not (hand_empty ?robot))
      (not (stacked_on ?obj_top ?obj_bottom))
      (not (on ?obj_top ?loc))
      (clear ?obj_bottom)
    )
  )
)
