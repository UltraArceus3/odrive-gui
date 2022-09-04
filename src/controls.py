from datetime import datetime
from typing import Any

import odrive.enums as enums
from nicegui import ui
from odrive.utils import dump_errors


def get_errors(err, enums):
    if err == 0:
        return [enums.NONE.name]
    enum_vals = [x.value for x in sorted(enums, reverse=True)]

    detected_errors = []
    for i in enum_vals:
        if err < i or err == 0:
            continue
        if err >= i:
            detected_errors.append(i)
            err -= i

    return [enums(x).name for x in detected_errors]


def controls(odrv):
    modes = {
        0: 'voltage',
        1: 'torque',
        2: 'velocity',
        3: 'position',
    }

    input_modes = {
        0: 'inactive',
        1: 'through',
        2: 'v-ramp',
        3: 'p-filter',
        5: 'trap traj',
        6: 't-ramp',
        7: 'mirror',
    }

    states = {
        0: 'undefined',
        1: 'idle',
        # 3: 'full calibration',
        4: 'motor calibration',
        6: 'index search',
        7: 'offset calibration',
        8: 'loop',
    }

    ui.markdown('## ODrive GUI')

    with ui.row().classes('items-center'):
        ui.label(f'SN {hex(odrv.serial_number).removeprefix("0x").upper()}')
        ui.label(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
        ui.label(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision} ' +
                 f'{"(dev)" if odrv.fw_version_unreleased else ""}')
        voltage = ui.label()
        ui.timer(1.0, lambda: voltage.set_text(f'{odrv.vbus_voltage:.2f} V'))
        ui.button(on_click=lambda: odrv.save_configuration()).props('icon=save flat round').tooltip('Save configuration')
        ui.button(on_click=lambda: dump_errors(odrv, True)).props('icon=bug_report flat round').tooltip('Dump errors')

    def axis_column(a: int, axis: Any) -> None:
        ui.markdown(f'### Axis {a}')

        power = ui.label()
        ui.timer(0.1, lambda: power.set_text(
            f'{axis.motor.current_control.Iq_measured * axis.motor.current_control.v_current_control_integral_q:.1f} W, '
            + f'{axis.motor.current_control.Iq_measured} Amp'
        ))

        axi_err = get_errors(axis.error, enums.AxisError)
        mot_err = get_errors(axis.motor.error, enums.MotorError)
        enc_err = get_errors(axis.encoder.error, enums.EncoderError)
        con_err = get_errors(axis.controller.error, enums.ControllerError)

        axis_error = ui.label()
        ui.timer(1.0, lambda: axis_error.set_text("Axis Errors: " + ", ".join(axi_err)))
        motor_error = ui.label()
        ui.timer(1.0, lambda: motor_error.set_text("Motor Errors: " + ", ".join(mot_err)))
        encoder_error = ui.label()
        ui.timer(1.0, lambda: encoder_error.set_text("Encoder Errors: " + ", ".join(enc_err)))
        controller_error = ui.label()
        ui.timer(1.0, lambda: controller_error.set_text("Controller Errors: " + ", ".join(con_err)))

        ctr_cfg = axis.controller.config
        mtr_cfg = axis.motor.config
        enc_cfg = axis.encoder.config
        trp_cfg = axis.trap_traj.config

        with ui.row():
            mode = ui.toggle(modes).bind_value(ctr_cfg, 'control_mode')
            ui.toggle(states) \
                .bind_value_to(axis, 'requested_state', forward=lambda x: x or 0) \
                .bind_value_from(axis, 'current_state')

        with ui.row():
            with ui.card().bind_visibility_from(mode, 'value', value=1):
                ui.markdown('**Torque**')
                torque = ui.number('input torque', value=0)
                def send_torque(sign: int) -> None: axis.controller.input_torque = sign * float(torque.value)
                with ui.row():
                    ui.button(on_click=lambda: send_torque(-1)).props('round flat icon=remove')
                    ui.button(on_click=lambda: send_torque(0)).props('round flat icon=radio_button_unchecked')
                    ui.button(on_click=lambda: send_torque(1)).props('round flat icon=add')

            with ui.card().bind_visibility_from(mode, 'value', value=2):
                ui.markdown('**Velocity**')
                velocity = ui.number('input velocity', value=0)
                def send_velocity(sign: int) -> None: axis.controller.input_vel = sign * float(velocity.value)
                with ui.row():
                    ui.button(on_click=lambda: send_velocity(-1)).props('round flat icon=fast_rewind')
                    ui.button(on_click=lambda: send_velocity(0)).props('round flat icon=stop')
                    ui.button(on_click=lambda: send_velocity(1)).props('round flat icon=fast_forward')

            with ui.card().bind_visibility_from(mode, 'value', value=3):
                ui.markdown('**Position**')
                position = ui.number('input position', value=0)
                def send_position(sign: int) -> None: axis.controller.input_pos = sign * float(position.value)
                with ui.row():
                    ui.button(on_click=lambda: send_position(-1)).props('round flat icon=skip_previous')
                    ui.button(on_click=lambda: send_position(0)).props('round flat icon=exposure_zero')
                    ui.button(on_click=lambda: send_position(1)).props('round flat icon=skip_next')

            with ui.column():
                ui.number('pos_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'pos_gain')
                ui.number('vel_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_gain')
                ui.number('vel_integrator_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_integrator_gain')
                if hasattr(ctr_cfg, 'vel_differentiator_gain'):
                    ui.number('vel_differentiator_gain', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_differentiator_gain')

            with ui.column():
                ui.number('vel_limit', format='%.3f').props('outlined').bind_value(ctr_cfg, 'vel_limit')
                ui.number('enc_bandwidth', format='%.3f').props('outlined').bind_value(enc_cfg, 'bandwidth')
                ui.number('current_lim', format='%.1f').props('outlined').bind_value(mtr_cfg, 'current_lim')
                ui.number('cur_bandwidth', format='%.3f').props('outlined').bind_value(mtr_cfg, 'current_control_bandwidth')
                ui.number('torque_lim', format='%.1f').props('outlined').bind_value(mtr_cfg, 'torque_lim')
                ui.number('requested_cur_range', format='%.1f').props('outlined').bind_value(mtr_cfg, 'requested_current_range')

        input_mode = ui.toggle(input_modes).bind_value(ctr_cfg, 'input_mode')
        with ui.row():
            ui.number('inertia', format='%.3f').props('outlined') \
                .bind_value(ctr_cfg, 'inertia') \
                .bind_visibility_from(input_mode, 'value', backward=lambda m: m in [2, 3, 5])
            ui.number('velocity ramp rate', format='%.3f').props('outlined') \
                .bind_value(ctr_cfg, 'vel_ramp_rate') \
                .bind_visibility_from(input_mode, 'value', value=2)
            ui.number('input filter bandwidth', format='%.3f').props('outlined') \
                .bind_value(ctr_cfg, 'input_filter_bandwidth') \
                .bind_visibility_from(input_mode, 'value', value=3)
            ui.number('trajectory velocity limit', format='%.3f').props('outlined') \
                .bind_value(trp_cfg, 'vel_limit') \
                .bind_visibility_from(input_mode, 'value', value=5)
            ui.number('trajectory acceleration limit', format='%.3f').props('outlined') \
                .bind_value(trp_cfg, 'accel_limit') \
                .bind_visibility_from(input_mode, 'value', value=5)
            ui.number('trajectory deceleration limit', format='%.3f').props('outlined') \
                .bind_value(trp_cfg, 'decel_limit') \
                .bind_visibility_from(input_mode, 'value', value=5)
            ui.number('torque ramp rate', format='%.3f').props('outlined') \
                .bind_value(ctr_cfg, 'torque_ramp_rate') \
                .bind_visibility_from(input_mode, 'value', value=6)
            ui.number('mirror ratio', format='%.3f').props('outlined') \
                .bind_value(ctr_cfg, 'mirror_ratio') \
                .bind_visibility_from(input_mode, 'value', value=7)
            ui.toggle({0: 'axis 0', 1: 'axis 1'}) \
                .bind_value(ctr_cfg, 'axis_to_mirror') \
                .bind_visibility_from(input_mode, 'value', value=7)

        async def pos_push() -> None:
            pos_plot.push([datetime.now()], [[axis.controller.input_pos], [axis.encoder.pos_estimate]])
            await pos_plot.view.update()
        pos_check = ui.checkbox('Position plot')
        pos_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_pos', 'pos_estimate'], loc='upper left', ncol=2)
        pos_timer = ui.timer(0.05, pos_push)
        pos_check.bind_value_to(pos_plot, 'visible').bind_value_to(pos_timer, 'active')

        async def vel_push() -> None:
            vel_plot.push([datetime.now()], [[axis.controller.input_vel], [axis.encoder.vel_estimate]])
            await vel_plot.view.update()
        vel_check = ui.checkbox('Velocity plot')
        vel_plot = ui.line_plot(n=2, update_every=10).with_legend(['input_vel', 'vel_estimate'], loc='upper left', ncol=2)
        vel_timer = ui.timer(0.05, vel_push)
        vel_check.bind_value_to(vel_plot, 'visible').bind_value_to(vel_timer, 'active')

        async def id_push() -> None:
            id_plot.push([datetime.now()], [[axis.motor.current_control.Id_setpoint], [axis.motor.current_control.Id_measured]])
            await id_plot.view.update()
        id_check = ui.checkbox('Id plot')
        id_plot = ui.line_plot(n=2, update_every=10).with_legend(['Id_setpoint', 'Id_measured'], loc='upper left', ncol=2)
        id_timer = ui.timer(0.05, id_push)
        id_check.bind_value_to(id_plot, 'visible').bind_value_to(id_timer, 'active')

        async def iq_push() -> None:
            iq_plot.push([datetime.now()], [[axis.motor.current_control.Iq_setpoint], [axis.motor.current_control.Iq_measured]])
            await iq_plot.view.update()
        iq_check = ui.checkbox('Iq plot')
        iq_plot = ui.line_plot(n=2, update_every=10).with_legend(['Iq_setpoint', 'Iq_measured'], loc='upper left', ncol=2)
        iq_timer = ui.timer(0.05, iq_push)
        iq_check.bind_value_to(iq_plot, 'visible').bind_value_to(iq_timer, 'active')

        async def t_push() -> None:
            t_plot.push([datetime.now()], [[axis.motor.fet_thermistor.temperature]])
            await t_plot.view.update()
        t_check = ui.checkbox('Temperature plot')
        t_plot = ui.line_plot(n=1, update_every=10)
        t_timer = ui.timer(0.05, t_push)
        t_check.bind_value_to(t_plot, 'visible').bind_value_to(t_timer, 'active')

    with ui.row():
        for a, axis in enumerate([odrv.axis0, odrv.axis1]):
            with ui.card(), ui.column():
                axis_column(a, axis)
