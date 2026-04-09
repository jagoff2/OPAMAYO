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
void car_err_fun(double *nom_x, double *delta_x, double *out_2934523573218771115);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_5371402512076971663);
void car_H_mod_fun(double *state, double *out_3953472098719516564);
void car_f_fun(double *state, double dt, double *out_5297345033802508057);
void car_F_fun(double *state, double dt, double *out_1423519290380021637);
void car_h_25(double *state, double *unused, double *out_4933420802133920103);
void car_H_25(double *state, double *unused, double *out_950219726465148276);
void car_h_24(double *state, double *unused, double *out_8694227067506695354);
void car_H_24(double *state, double *unused, double *out_1795216335248843675);
void car_h_30(double *state, double *unused, double *out_5632050620821582328);
void car_H_30(double *state, double *unused, double *out_3468552684972396903);
void car_h_26(double *state, double *unused, double *out_4688540767919919893);
void car_H_26(double *state, double *unused, double *out_2791283592408907948);
void car_h_27(double *state, double *unused, double *out_5536736686810397620);
void car_H_27(double *state, double *unused, double *out_5692146756156340120);
void car_h_29(double *state, double *unused, double *out_9174186215064419970);
void car_H_29(double *state, double *unused, double *out_3978784029286789087);
void car_h_28(double *state, double *unused, double *out_7908334119238308351);
void car_H_28(double *state, double *unused, double *out_1103614987782741487);
void car_h_31(double *state, double *unused, double *out_1295971273879897753);
void car_H_31(double *state, double *unused, double *out_3417491694642259424);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}