(define (problem tabletop-task)
  (:domain tabletop)

  ; -----------------------------------------------------------------
  ; OBJECTS — filled in by Agent 1 (LLM scene parser)
  ; Format: <name> - <type>
  ; Example:
  ;   red_cube - object
  ;   zone_a - location
  ;   franka - robot
  ; -----------------------------------------------------------------
  (:objects
    {{OBJECTS}}
  )

  ; -----------------------------------------------------------------
  ; INIT — initial world state predicates, filled by Agent 1
  ; Example:
  ;   (on_table red_cube)
  ;   (clear red_cube)
  ;   (hand_empty franka)
  ;   (at franka zone_a)
  ;   (on red_cube zone_a)
  ; -----------------------------------------------------------------
  (:init
    {{INIT}}
  )

  ; -----------------------------------------------------------------
  ; GOAL — target state, filled by Agent 1 from NL goal
  ; Example (goal: "Move red cube to zone B"):
  ;   (and (in_zone red_cube zone_b))
  ; Example (goal: "Stack blue cylinder on red cube at zone C"):
  ;   (and (stacked_on blue_cylinder red_cube) (in_zone red_cube zone_c))
  ; -----------------------------------------------------------------
  (:goal
    (and
      {{GOAL}}
    )
  )
)
