# Kalman filter
The Kalman filter estimates the state of a linear system with Gaussian noise. It alternates two steps.
The predict step pushes the state estimate through the motion model and grows the covariance by the process noise Q.
The update step corrects the prediction with a measurement, using the measurement noise R.

# Kalman gain
The Kalman gain K weighs the measurement against the prediction. If R is small compared with the predicted
covariance, K is large and the filter trusts the measurement. If R is large, K is small and the filter trusts the prediction.

# Extended Kalman filter
For nonlinear models the extended Kalman filter (EKF) linearizes the motion and measurement models with their Jacobians
around the current estimate. It can diverge when the linearization is poor, for example with large heading errors.

# Particle filter
A particle filter represents the belief with weighted samples. Each step moves the particles with the motion model,
weights them by the measurement likelihood and resamples. It handles multimodal beliefs, such as global localization,
but needs many particles in high dimensions.
