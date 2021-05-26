%
% Script that compare the solution from the numerical solver
% for cases with analytical solution.
%

k = 0.9;                 % Spring constant
m = 0.01;                % Brick mass
d0 = 1.0;                % Initial deflection
init_con = [0 0];        % Brick starting pos and start speed.
times = [1.0 0.3]; %% 0.45];  % [end_integration_time peak_car_speed_time end_car_speed_time]
car_speeds = [0 0 0];   % [car_start_speed car_peak_speed car_end_speed]

%
% Starting from rest. Accelerated only by released spring.
%
[t1,x1,v1,xc1,vc1,d1,e1,p1,be1]=brick_spring(k,m,d0,init_con,times,car_speeds);
% Analytical solution
xa1 = d0 - d0 * cos(sqrt(k/m) * t1);
va1 = d0 * sqrt(k/m) * sin(sqrt(k/m) * t1);

%
% The brick is moving at 10 m/s when passing through x = 0.
%
init_con = [0 10];   % Move at 10 m/s initially
[t2,x2,v2,xc2,vc2,d2,e2,p2,be2]=brick_spring(k,m,d0,init_con,times,car_speeds);
% Analytic solution...
d1 = sqrt(d0^2 + (m/k) * 10^2);
phase = acos(d0/d1);
xa2 = d0 - d1 * cos(sqrt(k/m) * t2 + phase);
va2 = d1 * sqrt(k/m) * sin(sqrt(k/m) * t2 + phase);



% Now move car at constant speed 10 m/s
times = [0.7 0.3 0.7];
car_speeds = [10 10 10]; % Car moves at constant speed
[t3,x3,v3,xc3,vc3,d3,e3,p3,be3]=brick_spring(k,m,d0,init_con,times,car_speeds);
% Analytic solution.
xa3 = d0 + (10 * t3) - d0 * cos(sqrt(k/m) * t3);
va3 = 10 + d0 * sqrt(k/m) * sin(sqrt(k/m) * t3);


%
%  Plot the results
%

% Plot parameters
lw = 2; %linewidth
ms = 2; %markersize
mk = 'o'; %marker experiments
fontsize = 16;
fontsizelgd = 12;

%
% Plot the simulated and analytical speeds as function of time... 
%
figure; hold on;

hsim = plot(t1, v1, 'kx', t1, va1, 'r-',...
	    t2, v2, 'mx', t2, va2, 'r-',...
	    t3, v3, 'bx', t3, va3, 'r-');
% 	    t4, vc4, 'c-', t4, v4, 'c--');
set(hsim, 'LineWidth', lw);
set(hsim, 'MarkerSize', ms);
set(gca, 'FontSize', fontsize);
xlabel('time (s)', 'FontSize', fontsize,...
    'Interpreter', 'latex');
ylabel('Speed $v(t)$ (m/s)', 'FontSize', fontsize,...
    'Interpreter', 'latex');
lh(1) = legend({'From rest, ODE', 'From rest, analytic',...
	        '$v_0 = 10$~m/s, ODE', '$v_0 = 10$~m/s, analytic',...
	        '$v_{c0} = 10$~m/s and $v_0 = 10$~m/s, ODE', 'same, analytic\ldots'},...
	       	'Interpreter', 'latex');


% 
% Plot the simulated and analytic position solutions.
%
figure; hold on;
hsim = plot(t1, x1, 'ko', t1, xa1, 'k--',...
	    t2, x2, 'ro', t2, xa2, 'r--',...
	    t3, x3, 'bo', t3, xa3, 'b--');
set(hsim, 'LineWidth', lw);
set(hsim, 'MarkerSize', ms);
set(gca, 'FontSize', fontsize);
xlabel('time (s)', 'FontSize', fontsize,...
    'Interpreter', 'latex');
ylabel('Brick possition $x(t)$ (m)', 'FontSize', fontsize,...
    'Interpreter', 'latex');
lh(2) = legend({'From rest, ODE', 'Same, analytic',...
	        '$v_0 = 10$~m/s, ODE', 'Same, analytic',...
		'$v_{c0} = 10$~m/s and $v_0 = 10$~m/s, ODE', 'Same, analytic'},...
	       	'Interpreter', 'latex');
