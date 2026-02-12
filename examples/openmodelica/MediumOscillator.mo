model MediumOscillator
  parameter Real w = 2.0;
  parameter Real z = 0.15;
  Real x(start = 1);
  Real v(start = 0);
equation
  der(x) = v;
  der(v) = -w*w*x - 2*z*w*v;
end MediumOscillator;
