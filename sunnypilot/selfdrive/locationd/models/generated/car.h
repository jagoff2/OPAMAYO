#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_err_fun(double *nom_x, double *delta_x, double *out_6370693165361400209);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_4021354849948946748);
void car_H_mod_fun(double *state, double *out_9082436266452764986);
void car_f_fun(double *state, double dt, double *out_301039448800418561);
void car_F_fun(double *state, double dt, double *out_8849587764955933077);
void car_h_25(double *state, double *unused, double *out_8608965514295846434);
void car_H_25(double *state, double *unused, double *out_4178744441268100146);
void car_h_24(double *state, double *unused, double *out_7903193367266152036);
void car_H_24(double *state, double *unused, double *out_2396827365323417955);
void car_h_30(double *state, double *unused, double *out_8884159576580352323);
void car_H_30(double *state, double *unused, double *out_4308083388411340216);
void car_h_26(double *state, double *unused, double *out_2781640140847157933);
void car_H_26(double *state, double *unused, double *out_7920247760142156370);
void car_h_27(double *state, double *unused, double *out_1606202810502780655);
void car_H_27(double *state, double *unused, double *out_6482846700211765127);
void car_h_29(double *state, double *unused, double *out_1449016142151651510);
void car_H_29(double *state, double *unused, double *out_8196209427081316160);
void car_h_28(double *state, double *unused, double *out_6607876078163626300);
void car_H_28(double *state, double *unused, double *out_6232579155515989909);
void car_h_31(double *state, double *unused, double *out_1944839064529181823);
void car_H_31(double *state, double *unused, double *out_4148098479391139718);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}