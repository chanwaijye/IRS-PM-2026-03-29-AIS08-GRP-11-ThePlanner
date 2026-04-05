; IPC-1998 Logistics domain (simplified, typed STRIPS)
; Move packages between locations using trucks.
; Simplified from the full logistics domain (no airplanes/cities) to
; remain within :strips :typing :negative-preconditions.
(define (domain logistics)
  (:requirements :strips :typing :negative-preconditions)

  (:types package truck location)

  (:predicates
    (at-pkg   ?pkg - package ?loc - location) ; package is at location
    (at-truck ?trk - truck   ?loc - location) ; truck is at location
    (in-truck ?pkg - package ?trk - truck)    ; package is loaded in truck
  )

  ; load a package into a truck (both at same location)
  (:action load-truck
    :parameters (?pkg - package ?trk - truck ?loc - location)
    :precondition (and
      (at-pkg   ?pkg ?loc)
      (at-truck ?trk ?loc)
    )
    :effect (and
      (in-truck ?pkg ?trk)
      (not (at-pkg ?pkg ?loc))
    )
  )

  ; unload a package from a truck at the truck's current location
  (:action unload-truck
    :parameters (?pkg - package ?trk - truck ?loc - location)
    :precondition (and
      (in-truck ?pkg ?trk)
      (at-truck ?trk ?loc)
    )
    :effect (and
      (at-pkg   ?pkg ?loc)
      (not (in-truck ?pkg ?trk))
    )
  )

  ; drive truck from one location to another
  (:action drive-truck
    :parameters (?trk - truck ?src - location ?dst - location)
    :precondition (and
      (at-truck ?trk ?src)
    )
    :effect (and
      (at-truck ?trk ?dst)
      (not (at-truck ?trk ?src))
    )
  )
)
