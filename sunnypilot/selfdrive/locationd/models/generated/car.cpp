#include "car.h"

namespace {
#define DIM 9
#define EDIM 9
#define MEDIM 9
typedef void (*Hfun)(double *, double *, double *);

double mass;

void set_mass(double x){ mass = x;}

double rotational_inertia;

void set_rotational_inertia(double x){ rotational_inertia = x;}

double center_to_front;

void set_center_to_front(double x){ center_to_front = x;}

double center_to_rear;

void set_center_to_rear(double x){ center_to_rear = x;}

double stiffness_front;

void set_stiffness_front(double x){ stiffness_front = x;}

double stiffness_rear;

void set_stiffness_rear(double x){ stiffness_rear = x;}
const static double MAHA_THRESH_25 = 3.8414588206941227;
const static double MAHA_THRESH_24 = 5.991464547107981;
const static double MAHA_THRESH_30 = 3.8414588206941227;
const static double MAHA_THRESH_26 = 3.8414588206941227;
const static double MAHA_THRESH_27 = 3.8414588206941227;
const static double MAHA_THRESH_29 = 3.8414588206941227;
const static double MAHA_THRESH_28 = 3.8414588206941227;
const static double MAHA_THRESH_31 = 3.8414588206941227;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_6370693165361400209) {
   out_6370693165361400209[0] = delta_x[0] + nom_x[0];
   out_6370693165361400209[1] = delta_x[1] + nom_x[1];
   out_6370693165361400209[2] = delta_x[2] + nom_x[2];
   out_6370693165361400209[3] = delta_x[3] + nom_x[3];
   out_6370693165361400209[4] = delta_x[4] + nom_x[4];
   out_6370693165361400209[5] = delta_x[5] + nom_x[5];
   out_6370693165361400209[6] = delta_x[6] + nom_x[6];
   out_6370693165361400209[7] = delta_x[7] + nom_x[7];
   out_6370693165361400209[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_4021354849948946748) {
   out_4021354849948946748[0] = -nom_x[0] + true_x[0];
   out_4021354849948946748[1] = -nom_x[1] + true_x[1];
   out_4021354849948946748[2] = -nom_x[2] + true_x[2];
   out_4021354849948946748[3] = -nom_x[3] + true_x[3];
   out_4021354849948946748[4] = -nom_x[4] + true_x[4];
   out_4021354849948946748[5] = -nom_x[5] + true_x[5];
   out_4021354849948946748[6] = -nom_x[6] + true_x[6];
   out_4021354849948946748[7] = -nom_x[7] + true_x[7];
   out_4021354849948946748[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_9082436266452764986) {
   out_9082436266452764986[0] = 1.0;
   out_9082436266452764986[1] = 0.0;
   out_9082436266452764986[2] = 0.0;
   out_9082436266452764986[3] = 0.0;
   out_9082436266452764986[4] = 0.0;
   out_9082436266452764986[5] = 0.0;
   out_9082436266452764986[6] = 0.0;
   out_9082436266452764986[7] = 0.0;
   out_9082436266452764986[8] = 0.0;
   out_9082436266452764986[9] = 0.0;
   out_9082436266452764986[10] = 1.0;
   out_9082436266452764986[11] = 0.0;
   out_9082436266452764986[12] = 0.0;
   out_9082436266452764986[13] = 0.0;
   out_9082436266452764986[14] = 0.0;
   out_9082436266452764986[15] = 0.0;
   out_9082436266452764986[16] = 0.0;
   out_9082436266452764986[17] = 0.0;
   out_9082436266452764986[18] = 0.0;
   out_9082436266452764986[19] = 0.0;
   out_9082436266452764986[20] = 1.0;
   out_9082436266452764986[21] = 0.0;
   out_9082436266452764986[22] = 0.0;
   out_9082436266452764986[23] = 0.0;
   out_9082436266452764986[24] = 0.0;
   out_9082436266452764986[25] = 0.0;
   out_9082436266452764986[26] = 0.0;
   out_9082436266452764986[27] = 0.0;
   out_9082436266452764986[28] = 0.0;
   out_9082436266452764986[29] = 0.0;
   out_9082436266452764986[30] = 1.0;
   out_9082436266452764986[31] = 0.0;
   out_9082436266452764986[32] = 0.0;
   out_9082436266452764986[33] = 0.0;
   out_9082436266452764986[34] = 0.0;
   out_9082436266452764986[35] = 0.0;
   out_9082436266452764986[36] = 0.0;
   out_9082436266452764986[37] = 0.0;
   out_9082436266452764986[38] = 0.0;
   out_9082436266452764986[39] = 0.0;
   out_9082436266452764986[40] = 1.0;
   out_9082436266452764986[41] = 0.0;
   out_9082436266452764986[42] = 0.0;
   out_9082436266452764986[43] = 0.0;
   out_9082436266452764986[44] = 0.0;
   out_9082436266452764986[45] = 0.0;
   out_9082436266452764986[46] = 0.0;
   out_9082436266452764986[47] = 0.0;
   out_9082436266452764986[48] = 0.0;
   out_9082436266452764986[49] = 0.0;
   out_9082436266452764986[50] = 1.0;
   out_9082436266452764986[51] = 0.0;
   out_9082436266452764986[52] = 0.0;
   out_9082436266452764986[53] = 0.0;
   out_9082436266452764986[54] = 0.0;
   out_9082436266452764986[55] = 0.0;
   out_9082436266452764986[56] = 0.0;
   out_9082436266452764986[57] = 0.0;
   out_9082436266452764986[58] = 0.0;
   out_9082436266452764986[59] = 0.0;
   out_9082436266452764986[60] = 1.0;
   out_9082436266452764986[61] = 0.0;
   out_9082436266452764986[62] = 0.0;
   out_9082436266452764986[63] = 0.0;
   out_9082436266452764986[64] = 0.0;
   out_9082436266452764986[65] = 0.0;
   out_9082436266452764986[66] = 0.0;
   out_9082436266452764986[67] = 0.0;
   out_9082436266452764986[68] = 0.0;
   out_9082436266452764986[69] = 0.0;
   out_9082436266452764986[70] = 1.0;
   out_9082436266452764986[71] = 0.0;
   out_9082436266452764986[72] = 0.0;
   out_9082436266452764986[73] = 0.0;
   out_9082436266452764986[74] = 0.0;
   out_9082436266452764986[75] = 0.0;
   out_9082436266452764986[76] = 0.0;
   out_9082436266452764986[77] = 0.0;
   out_9082436266452764986[78] = 0.0;
   out_9082436266452764986[79] = 0.0;
   out_9082436266452764986[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_301039448800418561) {
   out_301039448800418561[0] = state[0];
   out_301039448800418561[1] = state[1];
   out_301039448800418561[2] = state[2];
   out_301039448800418561[3] = state[3];
   out_301039448800418561[4] = state[4];
   out_301039448800418561[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8100000000000005*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_301039448800418561[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_301039448800418561[7] = state[7];
   out_301039448800418561[8] = state[8];
}
void F_fun(double *state, double dt, double *out_8849587764955933077) {
   out_8849587764955933077[0] = 1;
   out_8849587764955933077[1] = 0;
   out_8849587764955933077[2] = 0;
   out_8849587764955933077[3] = 0;
   out_8849587764955933077[4] = 0;
   out_8849587764955933077[5] = 0;
   out_8849587764955933077[6] = 0;
   out_8849587764955933077[7] = 0;
   out_8849587764955933077[8] = 0;
   out_8849587764955933077[9] = 0;
   out_8849587764955933077[10] = 1;
   out_8849587764955933077[11] = 0;
   out_8849587764955933077[12] = 0;
   out_8849587764955933077[13] = 0;
   out_8849587764955933077[14] = 0;
   out_8849587764955933077[15] = 0;
   out_8849587764955933077[16] = 0;
   out_8849587764955933077[17] = 0;
   out_8849587764955933077[18] = 0;
   out_8849587764955933077[19] = 0;
   out_8849587764955933077[20] = 1;
   out_8849587764955933077[21] = 0;
   out_8849587764955933077[22] = 0;
   out_8849587764955933077[23] = 0;
   out_8849587764955933077[24] = 0;
   out_8849587764955933077[25] = 0;
   out_8849587764955933077[26] = 0;
   out_8849587764955933077[27] = 0;
   out_8849587764955933077[28] = 0;
   out_8849587764955933077[29] = 0;
   out_8849587764955933077[30] = 1;
   out_8849587764955933077[31] = 0;
   out_8849587764955933077[32] = 0;
   out_8849587764955933077[33] = 0;
   out_8849587764955933077[34] = 0;
   out_8849587764955933077[35] = 0;
   out_8849587764955933077[36] = 0;
   out_8849587764955933077[37] = 0;
   out_8849587764955933077[38] = 0;
   out_8849587764955933077[39] = 0;
   out_8849587764955933077[40] = 1;
   out_8849587764955933077[41] = 0;
   out_8849587764955933077[42] = 0;
   out_8849587764955933077[43] = 0;
   out_8849587764955933077[44] = 0;
   out_8849587764955933077[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_8849587764955933077[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_8849587764955933077[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_8849587764955933077[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_8849587764955933077[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_8849587764955933077[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_8849587764955933077[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_8849587764955933077[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_8849587764955933077[53] = -9.8100000000000005*dt;
   out_8849587764955933077[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_8849587764955933077[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_8849587764955933077[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_8849587764955933077[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_8849587764955933077[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_8849587764955933077[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_8849587764955933077[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_8849587764955933077[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_8849587764955933077[62] = 0;
   out_8849587764955933077[63] = 0;
   out_8849587764955933077[64] = 0;
   out_8849587764955933077[65] = 0;
   out_8849587764955933077[66] = 0;
   out_8849587764955933077[67] = 0;
   out_8849587764955933077[68] = 0;
   out_8849587764955933077[69] = 0;
   out_8849587764955933077[70] = 1;
   out_8849587764955933077[71] = 0;
   out_8849587764955933077[72] = 0;
   out_8849587764955933077[73] = 0;
   out_8849587764955933077[74] = 0;
   out_8849587764955933077[75] = 0;
   out_8849587764955933077[76] = 0;
   out_8849587764955933077[77] = 0;
   out_8849587764955933077[78] = 0;
   out_8849587764955933077[79] = 0;
   out_8849587764955933077[80] = 1;
}
void h_25(double *state, double *unused, double *out_8608965514295846434) {
   out_8608965514295846434[0] = state[6];
}
void H_25(double *state, double *unused, double *out_4178744441268100146) {
   out_4178744441268100146[0] = 0;
   out_4178744441268100146[1] = 0;
   out_4178744441268100146[2] = 0;
   out_4178744441268100146[3] = 0;
   out_4178744441268100146[4] = 0;
   out_4178744441268100146[5] = 0;
   out_4178744441268100146[6] = 1;
   out_4178744441268100146[7] = 0;
   out_4178744441268100146[8] = 0;
}
void h_24(double *state, double *unused, double *out_7903193367266152036) {
   out_7903193367266152036[0] = state[4];
   out_7903193367266152036[1] = state[5];
}
void H_24(double *state, double *unused, double *out_2396827365323417955) {
   out_2396827365323417955[0] = 0;
   out_2396827365323417955[1] = 0;
   out_2396827365323417955[2] = 0;
   out_2396827365323417955[3] = 0;
   out_2396827365323417955[4] = 1;
   out_2396827365323417955[5] = 0;
   out_2396827365323417955[6] = 0;
   out_2396827365323417955[7] = 0;
   out_2396827365323417955[8] = 0;
   out_2396827365323417955[9] = 0;
   out_2396827365323417955[10] = 0;
   out_2396827365323417955[11] = 0;
   out_2396827365323417955[12] = 0;
   out_2396827365323417955[13] = 0;
   out_2396827365323417955[14] = 1;
   out_2396827365323417955[15] = 0;
   out_2396827365323417955[16] = 0;
   out_2396827365323417955[17] = 0;
}
void h_30(double *state, double *unused, double *out_8884159576580352323) {
   out_8884159576580352323[0] = state[4];
}
void H_30(double *state, double *unused, double *out_4308083388411340216) {
   out_4308083388411340216[0] = 0;
   out_4308083388411340216[1] = 0;
   out_4308083388411340216[2] = 0;
   out_4308083388411340216[3] = 0;
   out_4308083388411340216[4] = 1;
   out_4308083388411340216[5] = 0;
   out_4308083388411340216[6] = 0;
   out_4308083388411340216[7] = 0;
   out_4308083388411340216[8] = 0;
}
void h_26(double *state, double *unused, double *out_2781640140847157933) {
   out_2781640140847157933[0] = state[7];
}
void H_26(double *state, double *unused, double *out_7920247760142156370) {
   out_7920247760142156370[0] = 0;
   out_7920247760142156370[1] = 0;
   out_7920247760142156370[2] = 0;
   out_7920247760142156370[3] = 0;
   out_7920247760142156370[4] = 0;
   out_7920247760142156370[5] = 0;
   out_7920247760142156370[6] = 0;
   out_7920247760142156370[7] = 1;
   out_7920247760142156370[8] = 0;
}
void h_27(double *state, double *unused, double *out_1606202810502780655) {
   out_1606202810502780655[0] = state[3];
}
void H_27(double *state, double *unused, double *out_6482846700211765127) {
   out_6482846700211765127[0] = 0;
   out_6482846700211765127[1] = 0;
   out_6482846700211765127[2] = 0;
   out_6482846700211765127[3] = 1;
   out_6482846700211765127[4] = 0;
   out_6482846700211765127[5] = 0;
   out_6482846700211765127[6] = 0;
   out_6482846700211765127[7] = 0;
   out_6482846700211765127[8] = 0;
}
void h_29(double *state, double *unused, double *out_1449016142151651510) {
   out_1449016142151651510[0] = state[1];
}
void H_29(double *state, double *unused, double *out_8196209427081316160) {
   out_8196209427081316160[0] = 0;
   out_8196209427081316160[1] = 1;
   out_8196209427081316160[2] = 0;
   out_8196209427081316160[3] = 0;
   out_8196209427081316160[4] = 0;
   out_8196209427081316160[5] = 0;
   out_8196209427081316160[6] = 0;
   out_8196209427081316160[7] = 0;
   out_8196209427081316160[8] = 0;
}
void h_28(double *state, double *unused, double *out_6607876078163626300) {
   out_6607876078163626300[0] = state[0];
}
void H_28(double *state, double *unused, double *out_6232579155515989909) {
   out_6232579155515989909[0] = 1;
   out_6232579155515989909[1] = 0;
   out_6232579155515989909[2] = 0;
   out_6232579155515989909[3] = 0;
   out_6232579155515989909[4] = 0;
   out_6232579155515989909[5] = 0;
   out_6232579155515989909[6] = 0;
   out_6232579155515989909[7] = 0;
   out_6232579155515989909[8] = 0;
}
void h_31(double *state, double *unused, double *out_1944839064529181823) {
   out_1944839064529181823[0] = state[8];
}
void H_31(double *state, double *unused, double *out_4148098479391139718) {
   out_4148098479391139718[0] = 0;
   out_4148098479391139718[1] = 0;
   out_4148098479391139718[2] = 0;
   out_4148098479391139718[3] = 0;
   out_4148098479391139718[4] = 0;
   out_4148098479391139718[5] = 0;
   out_4148098479391139718[6] = 0;
   out_4148098479391139718[7] = 0;
   out_4148098479391139718[8] = 1;
}
#include <eigen3/Eigen/Dense>
#include <iostream>

typedef Eigen::Matrix<double, DIM, DIM, Eigen::RowMajor> DDM;
typedef Eigen::Matrix<double, EDIM, EDIM, Eigen::RowMajor> EEM;
typedef Eigen::Matrix<double, DIM, EDIM, Eigen::RowMajor> DEM;

void predict(double *in_x, double *in_P, double *in_Q, double dt) {
  typedef Eigen::Matrix<double, MEDIM, MEDIM, Eigen::RowMajor> RRM;

  double nx[DIM] = {0};
  double in_F[EDIM*EDIM] = {0};

  // functions from sympy
  f_fun(in_x, dt, nx);
  F_fun(in_x, dt, in_F);


  EEM F(in_F);
  EEM P(in_P);
  EEM Q(in_Q);

  RRM F_main = F.topLeftCorner(MEDIM, MEDIM);
  P.topLeftCorner(MEDIM, MEDIM) = (F_main * P.topLeftCorner(MEDIM, MEDIM)) * F_main.transpose();
  P.topRightCorner(MEDIM, EDIM - MEDIM) = F_main * P.topRightCorner(MEDIM, EDIM - MEDIM);
  P.bottomLeftCorner(EDIM - MEDIM, MEDIM) = P.bottomLeftCorner(EDIM - MEDIM, MEDIM) * F_main.transpose();

  P = P + dt*Q;

  // copy out state
  memcpy(in_x, nx, DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
}

// note: extra_args dim only correct when null space projecting
// otherwise 1
template <int ZDIM, int EADIM, bool MAHA_TEST>
void update(double *in_x, double *in_P, Hfun h_fun, Hfun H_fun, Hfun Hea_fun, double *in_z, double *in_R, double *in_ea, double MAHA_THRESHOLD) {
  typedef Eigen::Matrix<double, ZDIM, ZDIM, Eigen::RowMajor> ZZM;
  typedef Eigen::Matrix<double, ZDIM, DIM, Eigen::RowMajor> ZDM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, EDIM, Eigen::RowMajor> XEM;
  //typedef Eigen::Matrix<double, EDIM, ZDIM, Eigen::RowMajor> EZM;
  typedef Eigen::Matrix<double, Eigen::Dynamic, 1> X1M;
  typedef Eigen::Matrix<double, Eigen::Dynamic, Eigen::Dynamic, Eigen::RowMajor> XXM;

  double in_hx[ZDIM] = {0};
  double in_H[ZDIM * DIM] = {0};
  double in_H_mod[EDIM * DIM] = {0};
  double delta_x[EDIM] = {0};
  double x_new[DIM] = {0};


  // state x, P
  Eigen::Matrix<double, ZDIM, 1> z(in_z);
  EEM P(in_P);
  ZZM pre_R(in_R);

  // functions from sympy
  h_fun(in_x, in_ea, in_hx);
  H_fun(in_x, in_ea, in_H);
  ZDM pre_H(in_H);

  // get y (y = z - hx)
  Eigen::Matrix<double, ZDIM, 1> pre_y(in_hx); pre_y = z - pre_y;
  X1M y; XXM H; XXM R;
  if (Hea_fun){
    typedef Eigen::Matrix<double, ZDIM, EADIM, Eigen::RowMajor> ZAM;
    double in_Hea[ZDIM * EADIM] = {0};
    Hea_fun(in_x, in_ea, in_Hea);
    ZAM Hea(in_Hea);
    XXM A = Hea.transpose().fullPivLu().kernel();


    y = A.transpose() * pre_y;
    H = A.transpose() * pre_H;
    R = A.transpose() * pre_R * A;
  } else {
    y = pre_y;
    H = pre_H;
    R = pre_R;
  }
  // get modified H
  H_mod_fun(in_x, in_H_mod);
  DEM H_mod(in_H_mod);
  XEM H_err = H * H_mod;

  // Do mahalobis distance test
  if (MAHA_TEST){
    XXM a = (H_err * P * H_err.transpose() + R).inverse();
    double maha_dist = y.transpose() * a * y;
    if (maha_dist > MAHA_THRESHOLD){
      R = 1.0e16 * R;
    }
  }

  // Outlier resilient weighting
  double weight = 1;//(1.5)/(1 + y.squaredNorm()/R.sum());

  // kalman gains and I_KH
  XXM S = ((H_err * P) * H_err.transpose()) + R/weight;
  XEM KT = S.fullPivLu().solve(H_err * P.transpose());
  //EZM K = KT.transpose(); TODO: WHY DOES THIS NOT COMPILE?
  //EZM K = S.fullPivLu().solve(H_err * P.transpose()).transpose();
  //std::cout << "Here is the matrix rot:\n" << K << std::endl;
  EEM I_KH = Eigen::Matrix<double, EDIM, EDIM>::Identity() - (KT.transpose() * H_err);

  // update state by injecting dx
  Eigen::Matrix<double, EDIM, 1> dx(delta_x);
  dx  = (KT.transpose() * y);
  memcpy(delta_x, dx.data(), EDIM * sizeof(double));
  err_fun(in_x, delta_x, x_new);
  Eigen::Matrix<double, DIM, 1> x(x_new);

  // update cov
  P = ((I_KH * P) * I_KH.transpose()) + ((KT.transpose() * R) * KT);

  // copy out state
  memcpy(in_x, x.data(), DIM * sizeof(double));
  memcpy(in_P, P.data(), EDIM * EDIM * sizeof(double));
  memcpy(in_z, y.data(), y.rows() * sizeof(double));
}




}
extern "C" {

void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_25, H_25, NULL, in_z, in_R, in_ea, MAHA_THRESH_25);
}
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<2, 3, 0>(in_x, in_P, h_24, H_24, NULL, in_z, in_R, in_ea, MAHA_THRESH_24);
}
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_30, H_30, NULL, in_z, in_R, in_ea, MAHA_THRESH_30);
}
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_26, H_26, NULL, in_z, in_R, in_ea, MAHA_THRESH_26);
}
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_27, H_27, NULL, in_z, in_R, in_ea, MAHA_THRESH_27);
}
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_29, H_29, NULL, in_z, in_R, in_ea, MAHA_THRESH_29);
}
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_28, H_28, NULL, in_z, in_R, in_ea, MAHA_THRESH_28);
}
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<1, 3, 0>(in_x, in_P, h_31, H_31, NULL, in_z, in_R, in_ea, MAHA_THRESH_31);
}
void car_err_fun(double *nom_x, double *delta_x, double *out_6370693165361400209) {
  err_fun(nom_x, delta_x, out_6370693165361400209);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_4021354849948946748) {
  inv_err_fun(nom_x, true_x, out_4021354849948946748);
}
void car_H_mod_fun(double *state, double *out_9082436266452764986) {
  H_mod_fun(state, out_9082436266452764986);
}
void car_f_fun(double *state, double dt, double *out_301039448800418561) {
  f_fun(state,  dt, out_301039448800418561);
}
void car_F_fun(double *state, double dt, double *out_8849587764955933077) {
  F_fun(state,  dt, out_8849587764955933077);
}
void car_h_25(double *state, double *unused, double *out_8608965514295846434) {
  h_25(state, unused, out_8608965514295846434);
}
void car_H_25(double *state, double *unused, double *out_4178744441268100146) {
  H_25(state, unused, out_4178744441268100146);
}
void car_h_24(double *state, double *unused, double *out_7903193367266152036) {
  h_24(state, unused, out_7903193367266152036);
}
void car_H_24(double *state, double *unused, double *out_2396827365323417955) {
  H_24(state, unused, out_2396827365323417955);
}
void car_h_30(double *state, double *unused, double *out_8884159576580352323) {
  h_30(state, unused, out_8884159576580352323);
}
void car_H_30(double *state, double *unused, double *out_4308083388411340216) {
  H_30(state, unused, out_4308083388411340216);
}
void car_h_26(double *state, double *unused, double *out_2781640140847157933) {
  h_26(state, unused, out_2781640140847157933);
}
void car_H_26(double *state, double *unused, double *out_7920247760142156370) {
  H_26(state, unused, out_7920247760142156370);
}
void car_h_27(double *state, double *unused, double *out_1606202810502780655) {
  h_27(state, unused, out_1606202810502780655);
}
void car_H_27(double *state, double *unused, double *out_6482846700211765127) {
  H_27(state, unused, out_6482846700211765127);
}
void car_h_29(double *state, double *unused, double *out_1449016142151651510) {
  h_29(state, unused, out_1449016142151651510);
}
void car_H_29(double *state, double *unused, double *out_8196209427081316160) {
  H_29(state, unused, out_8196209427081316160);
}
void car_h_28(double *state, double *unused, double *out_6607876078163626300) {
  h_28(state, unused, out_6607876078163626300);
}
void car_H_28(double *state, double *unused, double *out_6232579155515989909) {
  H_28(state, unused, out_6232579155515989909);
}
void car_h_31(double *state, double *unused, double *out_1944839064529181823) {
  h_31(state, unused, out_1944839064529181823);
}
void car_H_31(double *state, double *unused, double *out_4148098479391139718) {
  H_31(state, unused, out_4148098479391139718);
}
void car_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
void car_set_mass(double x) {
  set_mass(x);
}
void car_set_rotational_inertia(double x) {
  set_rotational_inertia(x);
}
void car_set_center_to_front(double x) {
  set_center_to_front(x);
}
void car_set_center_to_rear(double x) {
  set_center_to_rear(x);
}
void car_set_stiffness_front(double x) {
  set_stiffness_front(x);
}
void car_set_stiffness_rear(double x) {
  set_stiffness_rear(x);
}
}

const EKF car = {
  .name = "car",
  .kinds = { 25, 24, 30, 26, 27, 29, 28, 31 },
  .feature_kinds = {  },
  .f_fun = car_f_fun,
  .F_fun = car_F_fun,
  .err_fun = car_err_fun,
  .inv_err_fun = car_inv_err_fun,
  .H_mod_fun = car_H_mod_fun,
  .predict = car_predict,
  .hs = {
    { 25, car_h_25 },
    { 24, car_h_24 },
    { 30, car_h_30 },
    { 26, car_h_26 },
    { 27, car_h_27 },
    { 29, car_h_29 },
    { 28, car_h_28 },
    { 31, car_h_31 },
  },
  .Hs = {
    { 25, car_H_25 },
    { 24, car_H_24 },
    { 30, car_H_30 },
    { 26, car_H_26 },
    { 27, car_H_27 },
    { 29, car_H_29 },
    { 28, car_H_28 },
    { 31, car_H_31 },
  },
  .updates = {
    { 25, car_update_25 },
    { 24, car_update_24 },
    { 30, car_update_30 },
    { 26, car_update_26 },
    { 27, car_update_27 },
    { 29, car_update_29 },
    { 28, car_update_28 },
    { 31, car_update_31 },
  },
  .Hes = {
  },
  .sets = {
    { "mass", car_set_mass },
    { "rotational_inertia", car_set_rotational_inertia },
    { "center_to_front", car_set_center_to_front },
    { "center_to_rear", car_set_center_to_rear },
    { "stiffness_front", car_set_stiffness_front },
    { "stiffness_rear", car_set_stiffness_rear },
  },
  .extra_routines = {
  },
};

ekf_lib_init(car)
