; IPC Blocksworld p02 — 3 blocks, build tower from table
; Init:  a, b, c all on table (clear)
; Goal:  a on b, b on c           a
;                                 b
;                                 c
; Optimal plan length: 4
;   1. pick-up(b)  2. stack(b,c)  3. pick-up(a)  4. stack(a,b)
(define (problem blocksworld-p02)
  (:domain blocksworld)
  (:objects a b c - block)
  (:init
    (ontable a)
    (ontable b)
    (ontable c)
    (clear a)
    (clear b)
    (clear c)
    (handempty)
  )
  (:goal (and
    (on a b)
    (on b c)
  ))
)
