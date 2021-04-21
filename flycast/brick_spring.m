function [time,x,v,cx,cv,sd,se,cp,be]=brick_spring(k,m,d0,init_con,times,car_speeds)
%BRICK_SPRING solves the brick in a pulled spring problem using Matlab's ode solver.
% [time,x,v,cx,cv,sd,se,cp,be] = BRICK_SPRING(k, m, d0, intit_con, times, car_speeds)
% solves the brick in a pulled spring problem using Matlabs ode-solver.
% The parameters are:
%   k = spring konstant.
%   m = mass of attaced brick.
%   d0 = initial spring extension.
%   init_con = initial conditions: [x(t=0) v(t=0)]
%   times = [end time, car "turn time", car end time].
%   car_speeds = [car start speed, car peak speed, car end speed]
%
% The returned vectors are:
%   time = time vector from the ode-solver
%   x = vector with position of the mass
%   v = speed of the mass
%   cx = position of the car
%   cv = speed of the car
%   sd = spring extension
%   se = spring energy
%   cp = "car power"
%   be = "brick energy"
%

ode_init_step = 0.01;  % Initial step length in ODE solver
ode_max_step = 0.01;   % Max step length in ODE solver

options = odeset('Events',@events,'Refine',10,'InitialStep', ode_init_step,'MaxStep',ode_max_step);
t_turn = times(2);
if (max(size(times)) > 2)
    t_car_end = times(3);
else
    t_car_end = times(1);
end

time_int = [0 times(1)];
cv0 = car_speeds(1); % Initial car speed
a1 = (car_speeds(2) - car_speeds(1))/t_turn;
if(t_car_end > t_turn)
    a2 = (car_speeds(3) - car_speeds(2))/(t_car_end - t_turn);
elseif(t_car_end == t_turn)
    a2 = 0;  % This mean an "imediate stop"...
else
    'The car end speed time have to be larger or equal to the car turning time!'
    return
end

% Run the ode solver
[time,y] = ode45(@f,time_int,init_con,options);

x_car = [];
v_car = [];
for i=1:1:size(time)
    x_car(end + 1) = x_b(time(i));
    v_car(end + 1) = bxspeed(time(i));
end

x = y(:,1);              % Mass possition
v = y(:,2);              % Speed of mass
cx = x_car';             % "Car" position
cv = v_car';             % "Car" speed
sd = cx - x;             % Spring deflection
se = 0.5 * k * (sd.*sd); % Spring energy
cp = k * (cv .* sd);     % "Car" power
be = 0.5 * m * (v .* v); % "Brick" energy


%--------------------------------
% Internal functions
%

%
% Function for the derivative.
%
    function dydt = f(t,y)
        % Calculate the second time derivative
        dydt2 = -(k/m) * (y(1) - x_b(t));
        %
        % To add dissipation to the problem add the term:
        %    -ka * y(2) * abs(y(2))
        % to the equation above, ka is the air friction coeficient...
        %
        dydt = [y(2); dydt2];
    end


%
% Function to calculate the possition of the car as funtion of time
%
    function xbt = x_b(t)
        if(t <= t_turn)
            xbt = cv0 * t + 1/2 * a1 * t^2 + d0;
        elseif(t > t_turn && t <= t_car_end)
            xbt = cv0 * t_turn + 1/2 * a1  * t_turn^2 + d0 + ...
                (a1 * t_turn) * (t - t_turn) + 1/2 * a2 *(t - t_turn)^2;
        else
            xbt = x_b(t_car_end) + car_speeds(3) * (t - t_car_end);
        end
    end

%
% Function to calculate the speed of the car as function of time.
% Just the linear equation of motion formula...
%
    function bspeed = bxspeed(t)
        if(t <= t_turn)
            bspeed = cv0 + a1 * t;
        elseif(t > t_turn && t <= t_car_end)
            bspeed = cv0 + a1 * t_turn + a2 * (t - t_turn);
        else
            bspeed = car_speeds(3);
        end
    end

%
% Event function which stop the solver when the spring
% extension becomes 0.
%
    function [value,isterminal,direction] = events(t,y)
        value =  x_b(t) - y(1);
        isterminal = 1;         % Stop integration
        direction = -1;         % Negative direction (spring compression)
    end

end % of brick_spring function