; IPC Logistics p01 — 2 packages, 1 truck, 2 locations
; Deliver both packages from loc1 to loc2 using one truck.
; Optimal plan length: 5
;   1. load-truck(pkg1,truck1,loc1)
;   2. load-truck(pkg2,truck1,loc1)
;   3. drive-truck(truck1,loc1,loc2)
;   4. unload-truck(pkg1,truck1,loc2)
;   5. unload-truck(pkg2,truck1,loc2)
(define (problem logistics-p01)
  (:domain logistics)
  (:objects
    pkg1 pkg2 - package
    truck1    - truck
    loc1 loc2 - location
  )
  (:init
    (at-pkg   pkg1   loc1)
    (at-pkg   pkg2   loc1)
    (at-truck truck1 loc1)
  )
  (:goal (and
    (at-pkg pkg1 loc2)
    (at-pkg pkg2 loc2)
  ))
)
