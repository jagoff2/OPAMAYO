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
void err_fun(double *nom_x, double *delta_x, double *out_2934523573218771115) {
   out_2934523573218771115[0] = delta_x[0] + nom_x[0];
   out_2934523573218771115[1] = delta_x[1] + nom_x[1];
   out_2934523573218771115[2] = delta_x[2] + nom_x[2];
   out_2934523573218771115[3] = delta_x[3] + nom_x[3];
   out_2934523573218771115[4] = delta_x[4] + nom_x[4];
   out_2934523573218771115[5] = delta_x[5] + nom_x[5];
   out_2934523573218771115[6] = delta_x[6] + nom_x[6];
   out_2934523573218771115[7] = delta_x[7] + nom_x[7];
   out_2934523573218771115[8] = delta_x[8] + nom_x[8];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_5371402512076971663) {
   out_5371402512076971663[0] = -nom_x[0] + true_x[0];
   out_5371402512076971663[1] = -nom_x[1] + true_x[1];
   out_5371402512076971663[2] = -nom_x[2] + true_x[2];
   out_5371402512076971663[3] = -nom_x[3] + true_x[3];
   out_5371402512076971663[4] = -nom_x[4] + true_x[4];
   out_5371402512076971663[5] = -nom_x[5] + true_x[5];
   out_5371402512076971663[6] = -nom_x[6] + true_x[6];
   out_5371402512076971663[7] = -nom_x[7] + true_x[7];
   out_5371402512076971663[8] = -nom_x[8] + true_x[8];
}
void H_mod_fun(double *state, double *out_3953472098719516564) {
   out_3953472098719516564[0] = 1.0;
   out_3953472098719516564[1] = 0.0;
   out_3953472098719516564[2] = 0.0;
   out_3953472098719516564[3] = 0.0;
   out_3953472098719516564[4] = 0.0;
   out_3953472098719516564[5] = 0.0;
   out_3953472098719516564[6] = 0.0;
   out_3953472098719516564[7] = 0.0;
   out_3953472098719516564[8] = 0.0;
   out_3953472098719516564[9] = 0.0;
   out_3953472098719516564[10] = 1.0;
   out_3953472098719516564[11] = 0.0;
   out_3953472098719516564[12] = 0.0;
   out_3953472098719516564[13] = 0.0;
   out_3953472098719516564[14] = 0.0;
   out_3953472098719516564[15] = 0.0;
   out_3953472098719516564[16] = 0.0;
   out_3953472098719516564[17] = 0.0;
   out_3953472098719516564[18] = 0.0;
   out_3953472098719516564[19] = 0.0;
   out_3953472098719516564[20] = 1.0;
   out_3953472098719516564[21] = 0.0;
   out_3953472098719516564[22] = 0.0;
   out_3953472098719516564[23] = 0.0;
   out_3953472098719516564[24] = 0.0;
   out_3953472098719516564[25] = 0.0;
   out_3953472098719516564[26] = 0.0;
   out_3953472098719516564[27] = 0.0;
   out_3953472098719516564[28] = 0.0;
   out_3953472098719516564[29] = 0.0;
   out_3953472098719516564[30] = 1.0;
   out_3953472098719516564[31] = 0.0;
   out_3953472098719516564[32] = 0.0;
   out_3953472098719516564[33] = 0.0;
   out_3953472098719516564[34] = 0.0;
   out_3953472098719516564[35] = 0.0;
   out_3953472098719516564[36] = 0.0;
   out_3953472098719516564[37] = 0.0;
   out_3953472098719516564[38] = 0.0;
   out_3953472098719516564[39] = 0.0;
   out_3953472098719516564[40] = 1.0;
   out_3953472098719516564[41] = 0.0;
   out_3953472098719516564[42] = 0.0;
   out_3953472098719516564[43] = 0.0;
   out_3953472098719516564[44] = 0.0;
   out_3953472098719516564[45] = 0.0;
   out_3953472098719516564[46] = 0.0;
   out_3953472098719516564[47] = 0.0;
   out_3953472098719516564[48] = 0.0;
   out_3953472098719516564[49] = 0.0;
   out_3953472098719516564[50] = 1.0;
   out_3953472098719516564[51] = 0.0;
   out_3953472098719516564[52] = 0.0;
   out_3953472098719516564[53] = 0.0;
   out_3953472098719516564[54] = 0.0;
   out_3953472098719516564[55] = 0.0;
   out_3953472098719516564[56] = 0.0;
   out_3953472098719516564[57] = 0.0;
   out_3953472098719516564[58] = 0.0;
   out_3953472098719516564[59] = 0.0;
   out_3953472098719516564[60] = 1.0;
   out_3953472098719516564[61] = 0.0;
   out_3953472098719516564[62] = 0.0;
   out_3953472098719516564[63] = 0.0;
   out_3953472098719516564[64] = 0.0;
   out_3953472098719516564[65] = 0.0;
   out_3953472098719516564[66] = 0.0;
   out_3953472098719516564[67] = 0.0;
   out_3953472098719516564[68] = 0.0;
   out_3953472098719516564[69] = 0.0;
   out_3953472098719516564[70] = 1.0;
   out_3953472098719516564[71] = 0.0;
   out_3953472098719516564[72] = 0.0;
   out_3953472098719516564[73] = 0.0;
   out_3953472098719516564[74] = 0.0;
   out_3953472098719516564[75] = 0.0;
   out_3953472098719516564[76] = 0.0;
   out_3953472098719516564[77] = 0.0;
   out_3953472098719516564[78] = 0.0;
   out_3953472098719516564[79] = 0.0;
   out_3953472098719516564[80] = 1.0;
}
void f_fun(double *state, double dt, double *out_5297345033802508057) {
   out_5297345033802508057[0] = state[0];
   out_5297345033802508057[1] = state[1];
   out_5297345033802508057[2] = state[2];
   out_5297345033802508057[3] = state[3];
   out_5297345033802508057[4] = state[4];
   out_5297345033802508057[5] = dt*((-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]))*state[6] - 9.8100000000000005*state[8] + stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*state[1]) + (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*state[4])) + state[5];
   out_5297345033802508057[6] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*state[4])) + state[6];
   out_5297345033802508057[7] = state[7];
   out_5297345033802508057[8] = state[8];
}
void F_fun(double *state, double dt, double *out_1423519290380021637) {
   out_1423519290380021637[0] = 1;
   out_1423519290380021637[1] = 0;
   out_1423519290380021637[2] = 0;
   out_1423519290380021637[3] = 0;
   out_1423519290380021637[4] = 0;
   out_1423519290380021637[5] = 0;
   out_1423519290380021637[6] = 0;
   out_1423519290380021637[7] = 0;
   out_1423519290380021637[8] = 0;
   out_1423519290380021637[9] = 0;
   out_1423519290380021637[10] = 1;
   out_1423519290380021637[11] = 0;
   out_1423519290380021637[12] = 0;
   out_1423519290380021637[13] = 0;
   out_1423519290380021637[14] = 0;
   out_1423519290380021637[15] = 0;
   out_1423519290380021637[16] = 0;
   out_1423519290380021637[17] = 0;
   out_1423519290380021637[18] = 0;
   out_1423519290380021637[19] = 0;
   out_1423519290380021637[20] = 1;
   out_1423519290380021637[21] = 0;
   out_1423519290380021637[22] = 0;
   out_1423519290380021637[23] = 0;
   out_1423519290380021637[24] = 0;
   out_1423519290380021637[25] = 0;
   out_1423519290380021637[26] = 0;
   out_1423519290380021637[27] = 0;
   out_1423519290380021637[28] = 0;
   out_1423519290380021637[29] = 0;
   out_1423519290380021637[30] = 1;
   out_1423519290380021637[31] = 0;
   out_1423519290380021637[32] = 0;
   out_1423519290380021637[33] = 0;
   out_1423519290380021637[34] = 0;
   out_1423519290380021637[35] = 0;
   out_1423519290380021637[36] = 0;
   out_1423519290380021637[37] = 0;
   out_1423519290380021637[38] = 0;
   out_1423519290380021637[39] = 0;
   out_1423519290380021637[40] = 1;
   out_1423519290380021637[41] = 0;
   out_1423519290380021637[42] = 0;
   out_1423519290380021637[43] = 0;
   out_1423519290380021637[44] = 0;
   out_1423519290380021637[45] = dt*(stiffness_front*(-state[2] - state[3] + state[7])/(mass*state[1]) + (-stiffness_front - stiffness_rear)*state[5]/(mass*state[4]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[6]/(mass*state[4]));
   out_1423519290380021637[46] = -dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(mass*pow(state[1], 2));
   out_1423519290380021637[47] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_1423519290380021637[48] = -dt*stiffness_front*state[0]/(mass*state[1]);
   out_1423519290380021637[49] = dt*((-1 - (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*pow(state[4], 2)))*state[6] - (-stiffness_front*state[0] - stiffness_rear*state[0])*state[5]/(mass*pow(state[4], 2)));
   out_1423519290380021637[50] = dt*(-stiffness_front*state[0] - stiffness_rear*state[0])/(mass*state[4]) + 1;
   out_1423519290380021637[51] = dt*(-state[4] + (-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(mass*state[4]));
   out_1423519290380021637[52] = dt*stiffness_front*state[0]/(mass*state[1]);
   out_1423519290380021637[53] = -9.8100000000000005*dt;
   out_1423519290380021637[54] = dt*(center_to_front*stiffness_front*(-state[2] - state[3] + state[7])/(rotational_inertia*state[1]) + (-center_to_front*stiffness_front + center_to_rear*stiffness_rear)*state[5]/(rotational_inertia*state[4]) + (-pow(center_to_front, 2)*stiffness_front - pow(center_to_rear, 2)*stiffness_rear)*state[6]/(rotational_inertia*state[4]));
   out_1423519290380021637[55] = -center_to_front*dt*stiffness_front*(-state[2] - state[3] + state[7])*state[0]/(rotational_inertia*pow(state[1], 2));
   out_1423519290380021637[56] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_1423519290380021637[57] = -center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_1423519290380021637[58] = dt*(-(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])*state[5]/(rotational_inertia*pow(state[4], 2)) - (-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])*state[6]/(rotational_inertia*pow(state[4], 2)));
   out_1423519290380021637[59] = dt*(-center_to_front*stiffness_front*state[0] + center_to_rear*stiffness_rear*state[0])/(rotational_inertia*state[4]);
   out_1423519290380021637[60] = dt*(-pow(center_to_front, 2)*stiffness_front*state[0] - pow(center_to_rear, 2)*stiffness_rear*state[0])/(rotational_inertia*state[4]) + 1;
   out_1423519290380021637[61] = center_to_front*dt*stiffness_front*state[0]/(rotational_inertia*state[1]);
   out_1423519290380021637[62] = 0;
   out_1423519290380021637[63] = 0;
   out_1423519290380021637[64] = 0;
   out_1423519290380021637[65] = 0;
   out_1423519290380021637[66] = 0;
   out_1423519290380021637[67] = 0;
   out_1423519290380021637[68] = 0;
   out_1423519290380021637[69] = 0;
   out_1423519290380021637[70] = 1;
   out_1423519290380021637[71] = 0;
   out_1423519290380021637[72] = 0;
   out_1423519290380021637[73] = 0;
   out_1423519290380021637[74] = 0;
   out_1423519290380021637[75] = 0;
   out_1423519290380021637[76] = 0;
   out_1423519290380021637[77] = 0;
   out_1423519290380021637[78] = 0;
   out_1423519290380021637[79] = 0;
   out_1423519290380021637[80] = 1;
}
void h_25(double *state, double *unused, double *out_4933420802133920103) {
   out_4933420802133920103[0] = state[6];
}
void H_25(double *state, double *unused, double *out_950219726465148276) {
   out_950219726465148276[0] = 0;
   out_950219726465148276[1] = 0;
   out_950219726465148276[2] = 0;
   out_950219726465148276[3] = 0;
   out_950219726465148276[4] = 0;
   out_950219726465148276[5] = 0;
   out_950219726465148276[6] = 1;
   out_950219726465148276[7] = 0;
   out_950219726465148276[8] = 0;
}
void h_24(double *state, double *unused, double *out_8694227067506695354) {
   out_8694227067506695354[0] = state[4];
   out_8694227067506695354[1] = state[5];
}
void H_24(double *state, double *unused, double *out_1795216335248843675) {
   out_1795216335248843675[0] = 0;
   out_1795216335248843675[1] = 0;
   out_1795216335248843675[2] = 0;
   out_1795216335248843675[3] = 0;
   out_1795216335248843675[4] = 1;
   out_1795216335248843675[5] = 0;
   out_1795216335248843675[6] = 0;
   out_1795216335248843675[7] = 0;
   out_1795216335248843675[8] = 0;
   out_1795216335248843675[9] = 0;
   out_1795216335248843675[10] = 0;
   out_1795216335248843675[11] = 0;
   out_1795216335248843675[12] = 0;
   out_1795216335248843675[13] = 0;
   out_1795216335248843675[14] = 1;
   out_1795216335248843675[15] = 0;
   out_1795216335248843675[16] = 0;
   out_1795216335248843675[17] = 0;
}
void h_30(double *state, double *unused, double *out_5632050620821582328) {
   out_5632050620821582328[0] = state[4];
}
void H_30(double *state, double *unused, double *out_3468552684972396903) {
   out_3468552684972396903[0] = 0;
   out_3468552684972396903[1] = 0;
   out_3468552684972396903[2] = 0;
   out_3468552684972396903[3] = 0;
   out_3468552684972396903[4] = 1;
   out_3468552684972396903[5] = 0;
   out_3468552684972396903[6] = 0;
   out_3468552684972396903[7] = 0;
   out_3468552684972396903[8] = 0;
}
void h_26(double *state, double *unused, double *out_4688540767919919893) {
   out_4688540767919919893[0] = state[7];
}
void H_26(double *state, double *unused, double *out_2791283592408907948) {
   out_2791283592408907948[0] = 0;
   out_2791283592408907948[1] = 0;
   out_2791283592408907948[2] = 0;
   out_2791283592408907948[3] = 0;
   out_2791283592408907948[4] = 0;
   out_2791283592408907948[5] = 0;
   out_2791283592408907948[6] = 0;
   out_2791283592408907948[7] = 1;
   out_2791283592408907948[8] = 0;
}
void h_27(double *state, double *unused, double *out_5536736686810397620) {
   out_5536736686810397620[0] = state[3];
}
void H_27(double *state, double *unused, double *out_5692146756156340120) {
   out_5692146756156340120[0] = 0;
   out_5692146756156340120[1] = 0;
   out_5692146756156340120[2] = 0;
   out_5692146756156340120[3] = 1;
   out_5692146756156340120[4] = 0;
   out_5692146756156340120[5] = 0;
   out_5692146756156340120[6] = 0;
   out_5692146756156340120[7] = 0;
   out_5692146756156340120[8] = 0;
}
void h_29(double *state, double *unused, double *out_9174186215064419970) {
   out_9174186215064419970[0] = state[1];
}
void H_29(double *state, double *unused, double *out_3978784029286789087) {
   out_3978784029286789087[0] = 0;
   out_3978784029286789087[1] = 1;
   out_3978784029286789087[2] = 0;
   out_3978784029286789087[3] = 0;
   out_3978784029286789087[4] = 0;
   out_3978784029286789087[5] = 0;
   out_3978784029286789087[6] = 0;
   out_3978784029286789087[7] = 0;
   out_3978784029286789087[8] = 0;
}
void h_28(double *state, double *unused, double *out_7908334119238308351) {
   out_7908334119238308351[0] = state[0];
}
void H_28(double *state, double *unused, double *out_1103614987782741487) {
   out_1103614987782741487[0] = 1;
   out_1103614987782741487[1] = 0;
   out_1103614987782741487[2] = 0;
   out_1103614987782741487[3] = 0;
   out_1103614987782741487[4] = 0;
   out_1103614987782741487[5] = 0;
   out_1103614987782741487[6] = 0;
   out_1103614987782741487[7] = 0;
   out_1103614987782741487[8] = 0;
}
void h_31(double *state, double *unused, double *out_1295971273879897753) {
   out_1295971273879897753[0] = state[8];
}
void H_31(double *state, double *unused, double *out_3417491694642259424) {
   out_3417491694642259424[0] = 0;
   out_3417491694642259424[1] = 0;
   out_3417491694642259424[2] = 0;
   out_3417491694642259424[3] = 0;
   out_3417491694642259424[4] = 0;
   out_3417491694642259424[5] = 0;
   out_3417491694642259424[6] = 0;
   out_3417491694642259424[7] = 0;
   out_3417491694642259424[8] = 1;
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
void car_err_fun(double *nom_x, double *delta_x, double *out_2934523573218771115) {
  err_fun(nom_x, delta_x, out_2934523573218771115);
}
void car_inv_err_fun(double *nom_x, double *true_x, double *out_5371402512076971663) {
  inv_err_fun(nom_x, true_x, out_5371402512076971663);
}
void car_H_mod_fun(double *state, double *out_3953472098719516564) {
  H_mod_fun(state, out_3953472098719516564);
}
void car_f_fun(double *state, double dt, double *out_5297345033802508057) {
  f_fun(state,  dt, out_5297345033802508057);
}
void car_F_fun(double *state, double dt, double *out_1423519290380021637) {
  F_fun(state,  dt, out_1423519290380021637);
}
void car_h_25(double *state, double *unused, double *out_4933420802133920103) {
  h_25(state, unused, out_4933420802133920103);
}
void car_H_25(double *state, double *unused, double *out_950219726465148276) {
  H_25(state, unused, out_950219726465148276);
}
void car_h_24(double *state, double *unused, double *out_8694227067506695354) {
  h_24(state, unused, out_8694227067506695354);
}
void car_H_24(double *state, double *unused, double *out_1795216335248843675) {
  H_24(state, unused, out_1795216335248843675);
}
void car_h_30(double *state, double *unused, double *out_5632050620821582328) {
  h_30(state, unused, out_5632050620821582328);
}
void car_H_30(double *state, double *unused, double *out_3468552684972396903) {
  H_30(state, unused, out_3468552684972396903);
}
void car_h_26(double *state, double *unused, double *out_4688540767919919893) {
  h_26(state, unused, out_4688540767919919893);
}
void car_H_26(double *state, double *unused, double *out_2791283592408907948) {
  H_26(state, unused, out_2791283592408907948);
}
void car_h_27(double *state, double *unused, double *out_5536736686810397620) {
  h_27(state, unused, out_5536736686810397620);
}
void car_H_27(double *state, double *unused, double *out_5692146756156340120) {
  H_27(state, unused, out_5692146756156340120);
}
void car_h_29(double *state, double *unused, double *out_9174186215064419970) {
  h_29(state, unused, out_9174186215064419970);
}
void car_H_29(double *state, double *unused, double *out_3978784029286789087) {
  H_29(state, unused, out_3978784029286789087);
}
void car_h_28(double *state, double *unused, double *out_7908334119238308351) {
  h_28(state, unused, out_7908334119238308351);
}
void car_H_28(double *state, double *unused, double *out_1103614987782741487) {
  H_28(state, unused, out_1103614987782741487);
}
void car_h_31(double *state, double *unused, double *out_1295971273879897753) {
  h_31(state, unused, out_1295971273879897753);
}
void car_H_31(double *state, double *unused, double *out_3417491694642259424) {
  H_31(state, unused, out_3417491694642259424);
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
