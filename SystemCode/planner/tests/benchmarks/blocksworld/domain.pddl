; IPC-1998 Blocksworld domain (typed STRIPS)
; Classic 4-operator formulation: pick-up, put-down, stack, unstack
; Adapted to use explicit :typing so ThePlanner's grounder can resolve objects.
(define (domain blocksworld)
  (:requirements :strips :typing :negative-preconditions)

  (:types block)

  (:predicates
    (on      ?top - block ?bot - block)  ; top is directly on bot
    (ontable ?x   - block)               ; x rests on the table
    (clear   ?x   - block)               ; nothing on top of x
    (holding ?x   - block)               ; arm is holding x
    (handempty)                          ; arm is free (0-ary)
  )

  ; pick up a block from the table
  (:action pick-up
    :parameters (?x - block)
    :precondition (and
      (clear ?x)
      (ontable ?x)
      (handempty)
    )
    :effect (and
      (holding ?x)
      (not (clear ?x))
      (not (ontable ?x))
      (not (handempty))
    )
  )

  ; put a held block back on the table
  (:action put-down
    :parameters (?x - block)
    :precondition (and
      (holding ?x)
    )
    :effect (and
      (not (holding ?x))
      (clear ?x)
      (handempty)
      (ontable ?x)
    )
  )

  ; stack held block ?top onto clear block ?bot
  (:action stack
    :parameters (?top - block ?bot - block)
    :precondition (and
      (holding ?top)
      (clear ?bot)
    )
    :effect (and
      (on ?top ?bot)
      (clear ?top)
      (handempty)
      (not (holding ?top))
      (not (clear ?bot))
    )
  )

  ; unstack block ?top from block ?bot
  (:action unstack
    :parameters (?top - block ?bot - block)
    :precondition (and
      (on ?top ?bot)
      (clear ?top)
      (handempty)
    )
    :effect (and
      (holding ?top)
      (clear ?bot)
      (not (on ?top ?bot))
      (not (clear ?top))
      (not (handempty))
    )
  )
)
