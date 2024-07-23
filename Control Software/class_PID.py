import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
regressor = LinearRegression()
from scipy.optimize import differential_evolution


class class_PID:
    def __init__(self):
        self.end = False
        self.target_temp = -1 # initialize targeted temperature
        self.time_delta = pd.Timedelta(10, 'min') # initialize pid calculations interval
        self.PID = [0, 0, 0] # initialize pid values
        self.min_relative_cooling_time = 1/60
        self.max_relative_cooling_time = 1
        self.heating_rate = 0.6
        self.cooling_rate = 0.11

    def end_PID(self, end):
        if end==True:
            print(pd.Timestamp('now').strftime('%X'),'ended PID_obj')
            self.end = True
        elif end==False:
            self.end = False
    def PID_control(self, datetimes, temperatures):
        '''
        PID Cooling with control function:
        u(t) = P * e(t) + I * integral_0^t e(t~) dt~ + D * de(t)/dt
        with e(t) = T_target-T_sample as error function.

        self : object of class PID
            with parameters PID, target_temp, time_delta
        datetimes : numpy array of datetime64
            datetime values of the data
        temperatures : numpy array of floats
            temperature values
        target_temp : float
            targeted temperature to be reached
        time_delta : timedelta64
            time interval size for PID calculation
        PID : list or array of floats (3,)
            proportional, integral and derivative factor. Strongly dependet on system properties.
        -------
        relative_heating_time, relative_cooling_time : tuple of values [0,1]
            relative time to activate heating/cooling system
        '''
        ### Setup parameter limits for temperature control
        # make sure to open cooling valve every x seconds (at least)
        min_relative_cooling_time = self.min_relative_cooling_time  # currently imported from gui as input parameter
        max_relative_cooling_time = self.max_relative_cooling_time
        # make sure to activate heater valve every x seconds (at least)
        min_relative_heating_time = 0.0
        if self.end == True:
            print(pd.Timestamp('now').strftime('%X'),'PID Control end==True')
            raise Exception('PID Control stopped!')
        else:
            # return default parameters if TimeDelta was not reached yet
            #print(pd.Timestamp('now').strftime('%X'),'First time:', datetimes[0], 'Last Value:', datetimes[-1])
            #if datetimes[-1] < datetimes[0] + self.time_delta:
            #    raise TimeoutError('PID needs more time to start: '+ f'{self.time_delta.total_seconds()-pd.to_timedelta(datetimes[-1]-datetimes[0]).total_seconds()} s')
            # select only values within timelimit of TimeDelta
            times = np.array(datetimes[datetimes > datetimes[-1] - self.time_delta], dtype='datetime64[s]')
            temps = np.array(temperatures[datetimes > datetimes[-1] - self.time_delta])


            time_seconds = times.astype('int64')
            error = float(self.target_temp) - temps
            # create linear regression for derivative term
            regressor.fit(time_seconds.reshape(-1, 1), error)
            slope = regressor.coef_[0]
            # calculate control value for given interval
            try:
                proportional = float(self.PID[0]) * error[-1]
                integral = float(self.PID[1]) * np.sum(error[:-1] * np.diff(time_seconds))
                derivative = float(self.PID[2]) * slope
                control = proportional + integral + derivative
            except Exception as error:
                print(error)
                raise Exception(error)
            # get relative time values for heating and cooling system
            control = np.clip(control, -100, 100) / 100
            #print(pd.Timestamp('now').strftime('%X'),'control', control)
            if control >= 0:
                relative_heating_time = max(control, min_relative_heating_time)
                relative_cooling_time = min(min_relative_cooling_time, max_relative_cooling_time)
            elif control < 0:
                relative_cooling_time = min(max(abs(control), min_relative_cooling_time), max_relative_cooling_time)
                relative_heating_time = min_relative_heating_time
            return relative_heating_time, relative_cooling_time


    def PID_autotune(self, datetimes, temperatures):
        '''
        Tunes PID parameters automatically via a differential evolution.
        The System properties are simulated with PID_simulation
        -------
        datetimes : numpy array of datetime64
        temperatures : numpy array of floats
        target_temp : float
            temperature being targeted
        time_delta : timedelta64
            calculate PID with latest temperature values in this timespan
        -------
        optimized_PID : array of floats with shape (3,)
            optimized proportional, integral and derivative factors
        '''

        if self.target_temp==-1:
            raise Exception('Please input a valid target temperature!')

        def PID_simulation(PID, *args):
            '''
            Simulates the temperature control system with given PID parameters and the latest temperature data.
            A plot is created showing the simulation process.
            -------
            PID : array of floats with shape (3,)
                DESCRIPTION.
            *args : tuple
                datetimes, temperatures, target_temp, time_delta from PID_autotune
            -------
            average_error : float
                average temperature error to targeted temperature.

            '''
            # Arguments for PID calculation
            args = args[0]
            datetimes_sim = args[0]
            temperatures_sim = args[1]
            PID_obj = args[2]
            target_temp = PID_obj.target_temp
            time_delta = PID_obj.time_delta

            times = datetimes_sim[datetimes_sim > datetimes_sim[-1] - 2 * time_delta]
            temps = temperatures_sim[datetimes_sim > datetimes_sim[-1] - 2 * time_delta]
            errors = np.abs(target_temp - temps)

            # Simulation parameters
            current_time = times[-1]
            current_temp = temps[-1]
            simulation_time = pd.Timedelta(4, 'h')
            time_step = pd.Timedelta(10, 's')

            # pbar = tqdm(total=simulation_time.astype('timedelta64[s]').astype('int64'), position=0, leave=True)
            while times[-1] < current_time + simulation_time:
                if self.end == True:
                    raise Exception('Autotuning Simulation stopped!')

                # simulate temperature change based on current PID control
                try:
                    if PID_obj.PID == [0, 0, 0]:
                        # initialize PID for first run of simulation if no input was provided
                        PID_obj.PID = [1, 1, 1]
                    relative_heating_time, relative_cooling_time = class_PID.PID_control(PID_obj, times, temps)
                except TimeoutError as error:
                    raise TimeoutError(error)
                except Exception as error:
                    raise Exception(error)
                temperature_change = relative_heating_time * PID_obj.heating_rate - relative_cooling_time * PID_obj.cooling_rate

                # calculate current temperature and error to target temp
                current_temp += temperature_change * int(time_step.seconds) + np.random.uniform(-0.1, 0.1, 1)
                errors = np.append(errors, abs(target_temp - current_temp))

                # add new values to arrays
                times = np.append(times, times[-1] + time_step)
                temps = np.append(temps, current_temp)

                # pbar.update(time_step.astype('timedelta64[s]').astype('int64'))
            # calculate average error per second
            average_error = np.mean(errors[times > times[-1] - time_delta])
            return average_error

        def callback_func(xk, convergence=None):
            print(pd.Timestamp('now').strftime('%X'),'Best PID yet:', xk[0], xk[1], xk[2], '\nnext iteration...')
            if self.end==True:
                raise StopIteration('PID Autotuning Iteration stopped!')

        PID_bounds = [(0, 100), (0, 1E-1), (0, 10)]  # Bounds for proportional, integral and derivative parameters
        other_params = (datetimes, temperatures, self)
        start_time = pd.Timestamp('now')
        print(pd.Timestamp('now').strftime('%X'), 'Now tuning PID parameters! for Target:', self.target_temp, 'K')
        try:
            result = differential_evolution(PID_simulation, PID_bounds, args=(other_params,), popsize=6, maxiter=6, tol=0.1,
                                            disp=False, polish=False, callback=callback_func)
        except TimeoutError as error:
            raise TimeoutError(error)
        except Exception as error:
            print(pd.Timestamp('now').strftime('%X'), 'class_PID.PID_autotune ', error)
            raise Exception(f'PID Autotuning stopped at differential evolution! {error}')
        optimized_PID = result.x
        print(pd.Timestamp('now').strftime('%X'),result.message, '\nPID Autotuning finished in:', (pd.Timestamp('now') - start_time).seconds, 's',
                ' with optimal PID: ', f'{optimized_PID[0]:.2g}, {optimized_PID[1]:.2g}, {optimized_PID[2]:.2g}')
        return optimized_PID














