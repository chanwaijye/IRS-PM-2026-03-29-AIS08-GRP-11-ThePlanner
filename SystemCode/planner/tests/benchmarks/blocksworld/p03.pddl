; IPC Blocksworld p03 — 4 blocks, build tall tower from table
; Init:  a, b, c, d all on table (clear)
; Goal:  d on c, c on b, b on a   d
;                                 c
;                                 b
;                                 a
; Optimal plan length: 6
;   1. pick-up(b)  2. stack(b,a)
;   3. pick-up(c)  4. stack(c,b)
;   5. pick-up(d)  6. stack(d,c)
(define (problem blocksworld-p03)
  (:domain blocksworld)
  (:objects a b c d - block)
  (:init
    (ontable a)
    (ontable b)
    (ontable c)
    (ontable d)
    (clear a)
    (clear b)
    (clear c)
    (clear d)
    (handempty)
  )
  (:goal (and
    (on b a)
    (on c b)
    (on d c)
  ))
)
