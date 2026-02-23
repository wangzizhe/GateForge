model MediumSimFail
  Real x(start = 1);
  Real v(start = 0);
equation
  der(x) = v;
  der(v) = 1 / (x - 1);
end MediumSimFail;
