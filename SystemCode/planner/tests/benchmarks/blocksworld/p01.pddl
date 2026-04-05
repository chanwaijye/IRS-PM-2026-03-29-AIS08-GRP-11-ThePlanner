; IPC Blocksworld p01 — 2 blocks, swap
; Init:  a on b (b on table)      a
;                                 b
; Goal:  b on a                   b
;                                 a
; Optimal plan length: 4
;   1. unstack(a,b)  2. put-down(a)  3. pick-up(b)  4. stack(b,a)
(define (problem blocksworld-p01)
  (:domain blocksworld)
  (:objects a b - block)
  (:init
    (on a b)
    (ontable b)
    (clear a)
    (handempty)
  )
  (:goal (and
    (on b a)
  ))
)
