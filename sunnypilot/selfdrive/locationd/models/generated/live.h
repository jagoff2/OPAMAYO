#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void live_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_9(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_12(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_35(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_32(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_33(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_H(double *in_vec, double *out_3291579122655517309);
void live_err_fun(double *nom_x, double *delta_x, double *out_90053204539833701);
void live_inv_err_fun(double *nom_x, double *true_x, double *out_8808668042510738809);
void live_H_mod_fun(double *state, double *out_1345647847661082813);
void live_f_fun(double *state, double dt, double *out_4183638550970444910);
void live_F_fun(double *state, double dt, double *out_1961483003769405983);
void live_h_4(double *state, double *unused, double *out_6627567256238301414);
void live_H_4(double *state, double *unused, double *out_4398527813658795159);
void live_h_9(double *state, double *unused, double *out_8201751737670854300);
void live_H_9(double *state, double *unused, double *out_6760997324786308987);
void live_h_10(double *state, double *unused, double *out_3073206475338751420);
void live_H_10(double *state, double *unused, double *out_6957760010382308494);
void live_h_12(double *state, double *unused, double *out_9193168953344342865);
void live_H_12(double *state, double *unused, double *out_1982730563383937837);
void live_h_35(double *state, double *unused, double *out_6182017523186760770);
void live_H_35(double *state, double *unused, double *out_3635524914043292256);
void live_h_32(double *state, double *unused, double *out_8554212264410935228);
void live_H_32(double *state, double *unused, double *out_7976529689776399144);
void live_h_13(double *state, double *unused, double *out_2748228221047554318);
void live_H_13(double *state, double *unused, double *out_2265457496176330299);
void live_h_14(double *state, double *unused, double *out_8201751737670854300);
void live_H_14(double *state, double *unused, double *out_6760997324786308987);
void live_h_33(double *state, double *unused, double *out_4210545811136531296);
void live_H_33(double *state, double *unused, double *out_484967909404434652);
void live_predict(double *in_x, double *in_P, double *in_Q, double dt);
}