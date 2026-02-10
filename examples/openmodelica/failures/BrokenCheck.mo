model BrokenCheck
  Real x;
equation
  // Undeclared variable `y` should fail model checking.
  x = y;
end BrokenCheck;
