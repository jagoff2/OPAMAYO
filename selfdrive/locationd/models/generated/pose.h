#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void pose_err_fun(double *nom_x, double *delta_x, double *out_675686294106479216);
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_1402524249024729268);
void pose_H_mod_fun(double *state, double *out_6550902768055423329);
void pose_f_fun(double *state, double dt, double *out_3370286758101883761);
void pose_F_fun(double *state, double dt, double *out_1397960411052043499);
void pose_h_4(double *state, double *unused, double *out_111977664207872713);
void pose_H_4(double *state, double *unused, double *out_2462081651858261163);
void pose_h_10(double *state, double *unused, double *out_1198457513949802947);
void pose_H_10(double *state, double *unused, double *out_5637433044053919992);
void pose_h_13(double *state, double *unused, double *out_6919936230217658492);
void pose_H_13(double *state, double *unused, double *out_5674355477190593964);
void pose_h_14(double *state, double *unused, double *out_6919825385847265547);
void pose_H_14(double *state, double *unused, double *out_6425322508197745692);
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt);
}