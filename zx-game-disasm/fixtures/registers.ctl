b $4000 Fixture for the register rows
D $4000 Rows in both styles.
R $4000 I:HL destination, DE source, B byte count
R $4000 I:A The attribute byte.
R $4000 I:C attribute
R $4000 O:A 1 if the key is held, 0 otherwise
R $4000 I:DE pointer to the string (bit 7 set marks the final character)
R $4000 O:HL unchanged
R $4000 I:IX Steering object record.
R $4000 O: updates the heading
R $4000 Used by #FOREACH(EREF$4000)(caller,#Rcaller,, and )
B $4000,8
