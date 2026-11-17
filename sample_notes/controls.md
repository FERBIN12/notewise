# PID control
A PID controller computes a command from the error between the setpoint and the measured value.
It adds three terms: a proportional term (gain Kp times the error), an integral term (Ki times the accumulated error)
and a derivative term (Kd times the rate of change of the error).

# Integral windup
When the actuator saturates, the integral term keeps growing even though the output cannot change.
This is called integral windup and it causes large overshoot once the error changes sign.
Common fixes are clamping the integrator or stopping integration while the output is saturated (conditional integration).

# Derivative kick
Taking the derivative of the error makes the output spike when the setpoint jumps. This is derivative kick.
Using the derivative of the measurement instead of the error avoids it. A low-pass filter on the derivative reduces noise.

# Tuning
Ziegler-Nichols tuning raises Kp until the loop oscillates steadily at the ultimate gain Ku with period Tu,
then sets the gains from Ku and Tu. It tends to give an aggressive response with about 25 percent overshoot.
