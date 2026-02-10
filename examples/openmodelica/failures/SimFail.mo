model SimFail
  Real x(start = 0.0);
equation
  der(x) = 1.0;
  assert(time < 0.2, "forced simulation failure");
end SimFail;
