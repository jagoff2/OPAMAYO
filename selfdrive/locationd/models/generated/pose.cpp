#include "pose.h"

namespace {
#define DIM 18
#define EDIM 18
#define MEDIM 18
typedef void (*Hfun)(double *, double *, double *);
const static double MAHA_THRESH_4 = 7.814727903251177;
const static double MAHA_THRESH_10 = 7.814727903251177;
const static double MAHA_THRESH_13 = 7.814727903251177;
const static double MAHA_THRESH_14 = 7.814727903251177;

/******************************************************************************
 *                      Code generated with SymPy 1.14.0                      *
 *                                                                            *
 *              See http://www.sympy.org/ for more information.               *
 *                                                                            *
 *                         This file is part of 'ekf'                         *
 ******************************************************************************/
void err_fun(double *nom_x, double *delta_x, double *out_675686294106479216) {
   out_675686294106479216[0] = delta_x[0] + nom_x[0];
   out_675686294106479216[1] = delta_x[1] + nom_x[1];
   out_675686294106479216[2] = delta_x[2] + nom_x[2];
   out_675686294106479216[3] = delta_x[3] + nom_x[3];
   out_675686294106479216[4] = delta_x[4] + nom_x[4];
   out_675686294106479216[5] = delta_x[5] + nom_x[5];
   out_675686294106479216[6] = delta_x[6] + nom_x[6];
   out_675686294106479216[7] = delta_x[7] + nom_x[7];
   out_675686294106479216[8] = delta_x[8] + nom_x[8];
   out_675686294106479216[9] = delta_x[9] + nom_x[9];
   out_675686294106479216[10] = delta_x[10] + nom_x[10];
   out_675686294106479216[11] = delta_x[11] + nom_x[11];
   out_675686294106479216[12] = delta_x[12] + nom_x[12];
   out_675686294106479216[13] = delta_x[13] + nom_x[13];
   out_675686294106479216[14] = delta_x[14] + nom_x[14];
   out_675686294106479216[15] = delta_x[15] + nom_x[15];
   out_675686294106479216[16] = delta_x[16] + nom_x[16];
   out_675686294106479216[17] = delta_x[17] + nom_x[17];
}
void inv_err_fun(double *nom_x, double *true_x, double *out_1402524249024729268) {
   out_1402524249024729268[0] = -nom_x[0] + true_x[0];
   out_1402524249024729268[1] = -nom_x[1] + true_x[1];
   out_1402524249024729268[2] = -nom_x[2] + true_x[2];
   out_1402524249024729268[3] = -nom_x[3] + true_x[3];
   out_1402524249024729268[4] = -nom_x[4] + true_x[4];
   out_1402524249024729268[5] = -nom_x[5] + true_x[5];
   out_1402524249024729268[6] = -nom_x[6] + true_x[6];
   out_1402524249024729268[7] = -nom_x[7] + true_x[7];
   out_1402524249024729268[8] = -nom_x[8] + true_x[8];
   out_1402524249024729268[9] = -nom_x[9] + true_x[9];
   out_1402524249024729268[10] = -nom_x[10] + true_x[10];
   out_1402524249024729268[11] = -nom_x[11] + true_x[11];
   out_1402524249024729268[12] = -nom_x[12] + true_x[12];
   out_1402524249024729268[13] = -nom_x[13] + true_x[13];
   out_1402524249024729268[14] = -nom_x[14] + true_x[14];
   out_1402524249024729268[15] = -nom_x[15] + true_x[15];
   out_1402524249024729268[16] = -nom_x[16] + true_x[16];
   out_1402524249024729268[17] = -nom_x[17] + true_x[17];
}
void H_mod_fun(double *state, double *out_6550902768055423329) {
   out_6550902768055423329[0] = 1.0;
   out_6550902768055423329[1] = 0.0;
   out_6550902768055423329[2] = 0.0;
   out_6550902768055423329[3] = 0.0;
   out_6550902768055423329[4] = 0.0;
   out_6550902768055423329[5] = 0.0;
   out_6550902768055423329[6] = 0.0;
   out_6550902768055423329[7] = 0.0;
   out_6550902768055423329[8] = 0.0;
   out_6550902768055423329[9] = 0.0;
   out_6550902768055423329[10] = 0.0;
   out_6550902768055423329[11] = 0.0;
   out_6550902768055423329[12] = 0.0;
   out_6550902768055423329[13] = 0.0;
   out_6550902768055423329[14] = 0.0;
   out_6550902768055423329[15] = 0.0;
   out_6550902768055423329[16] = 0.0;
   out_6550902768055423329[17] = 0.0;
   out_6550902768055423329[18] = 0.0;
   out_6550902768055423329[19] = 1.0;
   out_6550902768055423329[20] = 0.0;
   out_6550902768055423329[21] = 0.0;
   out_6550902768055423329[22] = 0.0;
   out_6550902768055423329[23] = 0.0;
   out_6550902768055423329[24] = 0.0;
   out_6550902768055423329[25] = 0.0;
   out_6550902768055423329[26] = 0.0;
   out_6550902768055423329[27] = 0.0;
   out_6550902768055423329[28] = 0.0;
   out_6550902768055423329[29] = 0.0;
   out_6550902768055423329[30] = 0.0;
   out_6550902768055423329[31] = 0.0;
   out_6550902768055423329[32] = 0.0;
   out_6550902768055423329[33] = 0.0;
   out_6550902768055423329[34] = 0.0;
   out_6550902768055423329[35] = 0.0;
   out_6550902768055423329[36] = 0.0;
   out_6550902768055423329[37] = 0.0;
   out_6550902768055423329[38] = 1.0;
   out_6550902768055423329[39] = 0.0;
   out_6550902768055423329[40] = 0.0;
   out_6550902768055423329[41] = 0.0;
   out_6550902768055423329[42] = 0.0;
   out_6550902768055423329[43] = 0.0;
   out_6550902768055423329[44] = 0.0;
   out_6550902768055423329[45] = 0.0;
   out_6550902768055423329[46] = 0.0;
   out_6550902768055423329[47] = 0.0;
   out_6550902768055423329[48] = 0.0;
   out_6550902768055423329[49] = 0.0;
   out_6550902768055423329[50] = 0.0;
   out_6550902768055423329[51] = 0.0;
   out_6550902768055423329[52] = 0.0;
   out_6550902768055423329[53] = 0.0;
   out_6550902768055423329[54] = 0.0;
   out_6550902768055423329[55] = 0.0;
   out_6550902768055423329[56] = 0.0;
   out_6550902768055423329[57] = 1.0;
   out_6550902768055423329[58] = 0.0;
   out_6550902768055423329[59] = 0.0;
   out_6550902768055423329[60] = 0.0;
   out_6550902768055423329[61] = 0.0;
   out_6550902768055423329[62] = 0.0;
   out_6550902768055423329[63] = 0.0;
   out_6550902768055423329[64] = 0.0;
   out_6550902768055423329[65] = 0.0;
   out_6550902768055423329[66] = 0.0;
   out_6550902768055423329[67] = 0.0;
   out_6550902768055423329[68] = 0.0;
   out_6550902768055423329[69] = 0.0;
   out_6550902768055423329[70] = 0.0;
   out_6550902768055423329[71] = 0.0;
   out_6550902768055423329[72] = 0.0;
   out_6550902768055423329[73] = 0.0;
   out_6550902768055423329[74] = 0.0;
   out_6550902768055423329[75] = 0.0;
   out_6550902768055423329[76] = 1.0;
   out_6550902768055423329[77] = 0.0;
   out_6550902768055423329[78] = 0.0;
   out_6550902768055423329[79] = 0.0;
   out_6550902768055423329[80] = 0.0;
   out_6550902768055423329[81] = 0.0;
   out_6550902768055423329[82] = 0.0;
   out_6550902768055423329[83] = 0.0;
   out_6550902768055423329[84] = 0.0;
   out_6550902768055423329[85] = 0.0;
   out_6550902768055423329[86] = 0.0;
   out_6550902768055423329[87] = 0.0;
   out_6550902768055423329[88] = 0.0;
   out_6550902768055423329[89] = 0.0;
   out_6550902768055423329[90] = 0.0;
   out_6550902768055423329[91] = 0.0;
   out_6550902768055423329[92] = 0.0;
   out_6550902768055423329[93] = 0.0;
   out_6550902768055423329[94] = 0.0;
   out_6550902768055423329[95] = 1.0;
   out_6550902768055423329[96] = 0.0;
   out_6550902768055423329[97] = 0.0;
   out_6550902768055423329[98] = 0.0;
   out_6550902768055423329[99] = 0.0;
   out_6550902768055423329[100] = 0.0;
   out_6550902768055423329[101] = 0.0;
   out_6550902768055423329[102] = 0.0;
   out_6550902768055423329[103] = 0.0;
   out_6550902768055423329[104] = 0.0;
   out_6550902768055423329[105] = 0.0;
   out_6550902768055423329[106] = 0.0;
   out_6550902768055423329[107] = 0.0;
   out_6550902768055423329[108] = 0.0;
   out_6550902768055423329[109] = 0.0;
   out_6550902768055423329[110] = 0.0;
   out_6550902768055423329[111] = 0.0;
   out_6550902768055423329[112] = 0.0;
   out_6550902768055423329[113] = 0.0;
   out_6550902768055423329[114] = 1.0;
   out_6550902768055423329[115] = 0.0;
   out_6550902768055423329[116] = 0.0;
   out_6550902768055423329[117] = 0.0;
   out_6550902768055423329[118] = 0.0;
   out_6550902768055423329[119] = 0.0;
   out_6550902768055423329[120] = 0.0;
   out_6550902768055423329[121] = 0.0;
   out_6550902768055423329[122] = 0.0;
   out_6550902768055423329[123] = 0.0;
   out_6550902768055423329[124] = 0.0;
   out_6550902768055423329[125] = 0.0;
   out_6550902768055423329[126] = 0.0;
   out_6550902768055423329[127] = 0.0;
   out_6550902768055423329[128] = 0.0;
   out_6550902768055423329[129] = 0.0;
   out_6550902768055423329[130] = 0.0;
   out_6550902768055423329[131] = 0.0;
   out_6550902768055423329[132] = 0.0;
   out_6550902768055423329[133] = 1.0;
   out_6550902768055423329[134] = 0.0;
   out_6550902768055423329[135] = 0.0;
   out_6550902768055423329[136] = 0.0;
   out_6550902768055423329[137] = 0.0;
   out_6550902768055423329[138] = 0.0;
   out_6550902768055423329[139] = 0.0;
   out_6550902768055423329[140] = 0.0;
   out_6550902768055423329[141] = 0.0;
   out_6550902768055423329[142] = 0.0;
   out_6550902768055423329[143] = 0.0;
   out_6550902768055423329[144] = 0.0;
   out_6550902768055423329[145] = 0.0;
   out_6550902768055423329[146] = 0.0;
   out_6550902768055423329[147] = 0.0;
   out_6550902768055423329[148] = 0.0;
   out_6550902768055423329[149] = 0.0;
   out_6550902768055423329[150] = 0.0;
   out_6550902768055423329[151] = 0.0;
   out_6550902768055423329[152] = 1.0;
   out_6550902768055423329[153] = 0.0;
   out_6550902768055423329[154] = 0.0;
   out_6550902768055423329[155] = 0.0;
   out_6550902768055423329[156] = 0.0;
   out_6550902768055423329[157] = 0.0;
   out_6550902768055423329[158] = 0.0;
   out_6550902768055423329[159] = 0.0;
   out_6550902768055423329[160] = 0.0;
   out_6550902768055423329[161] = 0.0;
   out_6550902768055423329[162] = 0.0;
   out_6550902768055423329[163] = 0.0;
   out_6550902768055423329[164] = 0.0;
   out_6550902768055423329[165] = 0.0;
   out_6550902768055423329[166] = 0.0;
   out_6550902768055423329[167] = 0.0;
   out_6550902768055423329[168] = 0.0;
   out_6550902768055423329[169] = 0.0;
   out_6550902768055423329[170] = 0.0;
   out_6550902768055423329[171] = 1.0;
   out_6550902768055423329[172] = 0.0;
   out_6550902768055423329[173] = 0.0;
   out_6550902768055423329[174] = 0.0;
   out_6550902768055423329[175] = 0.0;
   out_6550902768055423329[176] = 0.0;
   out_6550902768055423329[177] = 0.0;
   out_6550902768055423329[178] = 0.0;
   out_6550902768055423329[179] = 0.0;
   out_6550902768055423329[180] = 0.0;
   out_6550902768055423329[181] = 0.0;
   out_6550902768055423329[182] = 0.0;
   out_6550902768055423329[183] = 0.0;
   out_6550902768055423329[184] = 0.0;
   out_6550902768055423329[185] = 0.0;
   out_6550902768055423329[186] = 0.0;
   out_6550902768055423329[187] = 0.0;
   out_6550902768055423329[188] = 0.0;
   out_6550902768055423329[189] = 0.0;
   out_6550902768055423329[190] = 1.0;
   out_6550902768055423329[191] = 0.0;
   out_6550902768055423329[192] = 0.0;
   out_6550902768055423329[193] = 0.0;
   out_6550902768055423329[194] = 0.0;
   out_6550902768055423329[195] = 0.0;
   out_6550902768055423329[196] = 0.0;
   out_6550902768055423329[197] = 0.0;
   out_6550902768055423329[198] = 0.0;
   out_6550902768055423329[199] = 0.0;
   out_6550902768055423329[200] = 0.0;
   out_6550902768055423329[201] = 0.0;
   out_6550902768055423329[202] = 0.0;
   out_6550902768055423329[203] = 0.0;
   out_6550902768055423329[204] = 0.0;
   out_6550902768055423329[205] = 0.0;
   out_6550902768055423329[206] = 0.0;
   out_6550902768055423329[207] = 0.0;
   out_6550902768055423329[208] = 0.0;
   out_6550902768055423329[209] = 1.0;
   out_6550902768055423329[210] = 0.0;
   out_6550902768055423329[211] = 0.0;
   out_6550902768055423329[212] = 0.0;
   out_6550902768055423329[213] = 0.0;
   out_6550902768055423329[214] = 0.0;
   out_6550902768055423329[215] = 0.0;
   out_6550902768055423329[216] = 0.0;
   out_6550902768055423329[217] = 0.0;
   out_6550902768055423329[218] = 0.0;
   out_6550902768055423329[219] = 0.0;
   out_6550902768055423329[220] = 0.0;
   out_6550902768055423329[221] = 0.0;
   out_6550902768055423329[222] = 0.0;
   out_6550902768055423329[223] = 0.0;
   out_6550902768055423329[224] = 0.0;
   out_6550902768055423329[225] = 0.0;
   out_6550902768055423329[226] = 0.0;
   out_6550902768055423329[227] = 0.0;
   out_6550902768055423329[228] = 1.0;
   out_6550902768055423329[229] = 0.0;
   out_6550902768055423329[230] = 0.0;
   out_6550902768055423329[231] = 0.0;
   out_6550902768055423329[232] = 0.0;
   out_6550902768055423329[233] = 0.0;
   out_6550902768055423329[234] = 0.0;
   out_6550902768055423329[235] = 0.0;
   out_6550902768055423329[236] = 0.0;
   out_6550902768055423329[237] = 0.0;
   out_6550902768055423329[238] = 0.0;
   out_6550902768055423329[239] = 0.0;
   out_6550902768055423329[240] = 0.0;
   out_6550902768055423329[241] = 0.0;
   out_6550902768055423329[242] = 0.0;
   out_6550902768055423329[243] = 0.0;
   out_6550902768055423329[244] = 0.0;
   out_6550902768055423329[245] = 0.0;
   out_6550902768055423329[246] = 0.0;
   out_6550902768055423329[247] = 1.0;
   out_6550902768055423329[248] = 0.0;
   out_6550902768055423329[249] = 0.0;
   out_6550902768055423329[250] = 0.0;
   out_6550902768055423329[251] = 0.0;
   out_6550902768055423329[252] = 0.0;
   out_6550902768055423329[253] = 0.0;
   out_6550902768055423329[254] = 0.0;
   out_6550902768055423329[255] = 0.0;
   out_6550902768055423329[256] = 0.0;
   out_6550902768055423329[257] = 0.0;
   out_6550902768055423329[258] = 0.0;
   out_6550902768055423329[259] = 0.0;
   out_6550902768055423329[260] = 0.0;
   out_6550902768055423329[261] = 0.0;
   out_6550902768055423329[262] = 0.0;
   out_6550902768055423329[263] = 0.0;
   out_6550902768055423329[264] = 0.0;
   out_6550902768055423329[265] = 0.0;
   out_6550902768055423329[266] = 1.0;
   out_6550902768055423329[267] = 0.0;
   out_6550902768055423329[268] = 0.0;
   out_6550902768055423329[269] = 0.0;
   out_6550902768055423329[270] = 0.0;
   out_6550902768055423329[271] = 0.0;
   out_6550902768055423329[272] = 0.0;
   out_6550902768055423329[273] = 0.0;
   out_6550902768055423329[274] = 0.0;
   out_6550902768055423329[275] = 0.0;
   out_6550902768055423329[276] = 0.0;
   out_6550902768055423329[277] = 0.0;
   out_6550902768055423329[278] = 0.0;
   out_6550902768055423329[279] = 0.0;
   out_6550902768055423329[280] = 0.0;
   out_6550902768055423329[281] = 0.0;
   out_6550902768055423329[282] = 0.0;
   out_6550902768055423329[283] = 0.0;
   out_6550902768055423329[284] = 0.0;
   out_6550902768055423329[285] = 1.0;
   out_6550902768055423329[286] = 0.0;
   out_6550902768055423329[287] = 0.0;
   out_6550902768055423329[288] = 0.0;
   out_6550902768055423329[289] = 0.0;
   out_6550902768055423329[290] = 0.0;
   out_6550902768055423329[291] = 0.0;
   out_6550902768055423329[292] = 0.0;
   out_6550902768055423329[293] = 0.0;
   out_6550902768055423329[294] = 0.0;
   out_6550902768055423329[295] = 0.0;
   out_6550902768055423329[296] = 0.0;
   out_6550902768055423329[297] = 0.0;
   out_6550902768055423329[298] = 0.0;
   out_6550902768055423329[299] = 0.0;
   out_6550902768055423329[300] = 0.0;
   out_6550902768055423329[301] = 0.0;
   out_6550902768055423329[302] = 0.0;
   out_6550902768055423329[303] = 0.0;
   out_6550902768055423329[304] = 1.0;
   out_6550902768055423329[305] = 0.0;
   out_6550902768055423329[306] = 0.0;
   out_6550902768055423329[307] = 0.0;
   out_6550902768055423329[308] = 0.0;
   out_6550902768055423329[309] = 0.0;
   out_6550902768055423329[310] = 0.0;
   out_6550902768055423329[311] = 0.0;
   out_6550902768055423329[312] = 0.0;
   out_6550902768055423329[313] = 0.0;
   out_6550902768055423329[314] = 0.0;
   out_6550902768055423329[315] = 0.0;
   out_6550902768055423329[316] = 0.0;
   out_6550902768055423329[317] = 0.0;
   out_6550902768055423329[318] = 0.0;
   out_6550902768055423329[319] = 0.0;
   out_6550902768055423329[320] = 0.0;
   out_6550902768055423329[321] = 0.0;
   out_6550902768055423329[322] = 0.0;
   out_6550902768055423329[323] = 1.0;
}
void f_fun(double *state, double dt, double *out_3370286758101883761) {
   out_3370286758101883761[0] = atan2((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), -(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]));
   out_3370286758101883761[1] = asin(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]));
   out_3370286758101883761[2] = atan2(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), -(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]));
   out_3370286758101883761[3] = dt*state[12] + state[3];
   out_3370286758101883761[4] = dt*state[13] + state[4];
   out_3370286758101883761[5] = dt*state[14] + state[5];
   out_3370286758101883761[6] = state[6];
   out_3370286758101883761[7] = state[7];
   out_3370286758101883761[8] = state[8];
   out_3370286758101883761[9] = state[9];
   out_3370286758101883761[10] = state[10];
   out_3370286758101883761[11] = state[11];
   out_3370286758101883761[12] = state[12];
   out_3370286758101883761[13] = state[13];
   out_3370286758101883761[14] = state[14];
   out_3370286758101883761[15] = state[15];
   out_3370286758101883761[16] = state[16];
   out_3370286758101883761[17] = state[17];
}
void F_fun(double *state, double dt, double *out_1397960411052043499) {
   out_1397960411052043499[0] = ((-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*cos(state[0])*cos(state[1]) - sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*cos(state[0])*cos(state[1]) - sin(dt*state[6])*sin(state[0])*cos(dt*state[7])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_1397960411052043499[1] = ((-sin(dt*state[6])*sin(dt*state[8]) - sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*cos(state[1]) - (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*sin(state[1]) - sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(state[0]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*sin(state[1]) + (-sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) + sin(dt*state[8])*cos(dt*state[6]))*cos(state[1]) - sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(state[0]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_1397960411052043499[2] = 0;
   out_1397960411052043499[3] = 0;
   out_1397960411052043499[4] = 0;
   out_1397960411052043499[5] = 0;
   out_1397960411052043499[6] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(dt*cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) - dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_1397960411052043499[7] = (-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[6])*sin(dt*state[7])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[6])*sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) - dt*sin(dt*state[6])*sin(state[1])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + (-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))*(-dt*sin(dt*state[7])*cos(dt*state[6])*cos(state[0])*cos(state[1]) + dt*sin(dt*state[8])*sin(state[0])*cos(dt*state[6])*cos(dt*state[7])*cos(state[1]) - dt*sin(state[1])*cos(dt*state[6])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_1397960411052043499[8] = ((dt*sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + dt*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (dt*sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]))*(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2)) + ((dt*sin(dt*state[6])*sin(dt*state[8]) + dt*sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (-dt*sin(dt*state[6])*cos(dt*state[8]) + dt*sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]))*(-(sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) + (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) - sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/(pow(-(sin(dt*state[6])*sin(dt*state[8]) + sin(dt*state[7])*cos(dt*state[6])*cos(dt*state[8]))*sin(state[1]) + (-sin(dt*state[6])*cos(dt*state[8]) + sin(dt*state[7])*sin(dt*state[8])*cos(dt*state[6]))*sin(state[0])*cos(state[1]) + cos(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2) + pow((sin(dt*state[6])*sin(dt*state[7])*sin(dt*state[8]) + cos(dt*state[6])*cos(dt*state[8]))*sin(state[0])*cos(state[1]) - (sin(dt*state[6])*sin(dt*state[7])*cos(dt*state[8]) - sin(dt*state[8])*cos(dt*state[6]))*sin(state[1]) + sin(dt*state[6])*cos(dt*state[7])*cos(state[0])*cos(state[1]), 2));
   out_1397960411052043499[9] = 0;
   out_1397960411052043499[10] = 0;
   out_1397960411052043499[11] = 0;
   out_1397960411052043499[12] = 0;
   out_1397960411052043499[13] = 0;
   out_1397960411052043499[14] = 0;
   out_1397960411052043499[15] = 0;
   out_1397960411052043499[16] = 0;
   out_1397960411052043499[17] = 0;
   out_1397960411052043499[18] = (-sin(dt*state[7])*sin(state[0])*cos(state[1]) - sin(dt*state[8])*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_1397960411052043499[19] = (-sin(dt*state[7])*sin(state[1])*cos(state[0]) + sin(dt*state[8])*sin(state[0])*sin(state[1])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_1397960411052043499[20] = 0;
   out_1397960411052043499[21] = 0;
   out_1397960411052043499[22] = 0;
   out_1397960411052043499[23] = 0;
   out_1397960411052043499[24] = 0;
   out_1397960411052043499[25] = (dt*sin(dt*state[7])*sin(dt*state[8])*sin(state[0])*cos(state[1]) - dt*sin(dt*state[7])*sin(state[1])*cos(dt*state[8]) + dt*cos(dt*state[7])*cos(state[0])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_1397960411052043499[26] = (-dt*sin(dt*state[8])*sin(state[1])*cos(dt*state[7]) - dt*sin(state[0])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/sqrt(1 - pow(sin(dt*state[7])*cos(state[0])*cos(state[1]) - sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1]) + sin(state[1])*cos(dt*state[7])*cos(dt*state[8]), 2));
   out_1397960411052043499[27] = 0;
   out_1397960411052043499[28] = 0;
   out_1397960411052043499[29] = 0;
   out_1397960411052043499[30] = 0;
   out_1397960411052043499[31] = 0;
   out_1397960411052043499[32] = 0;
   out_1397960411052043499[33] = 0;
   out_1397960411052043499[34] = 0;
   out_1397960411052043499[35] = 0;
   out_1397960411052043499[36] = ((sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_1397960411052043499[37] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-sin(dt*state[7])*sin(state[2])*cos(state[0])*cos(state[1]) + sin(dt*state[8])*sin(state[0])*sin(state[2])*cos(dt*state[7])*cos(state[1]) - sin(state[1])*sin(state[2])*cos(dt*state[7])*cos(dt*state[8]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(-sin(dt*state[7])*cos(state[0])*cos(state[1])*cos(state[2]) + sin(dt*state[8])*sin(state[0])*cos(dt*state[7])*cos(state[1])*cos(state[2]) - sin(state[1])*cos(dt*state[7])*cos(dt*state[8])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_1397960411052043499[38] = ((-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (-sin(state[0])*sin(state[1])*sin(state[2]) - cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_1397960411052043499[39] = 0;
   out_1397960411052043499[40] = 0;
   out_1397960411052043499[41] = 0;
   out_1397960411052043499[42] = 0;
   out_1397960411052043499[43] = (-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))*(dt*(sin(state[0])*cos(state[2]) - sin(state[1])*sin(state[2])*cos(state[0]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*sin(state[2])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + ((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))*(dt*(-sin(state[0])*sin(state[2]) - sin(state[1])*cos(state[0])*cos(state[2]))*cos(dt*state[7]) - dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[7])*sin(dt*state[8]) - dt*sin(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_1397960411052043499[44] = (dt*(sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*sin(state[2])*cos(dt*state[7])*cos(state[1]))*(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2)) + (dt*(sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*cos(dt*state[7])*cos(dt*state[8]) - dt*sin(dt*state[8])*cos(dt*state[7])*cos(state[1])*cos(state[2]))*((-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) - (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) - sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]))/(pow(-(sin(state[0])*sin(state[2]) + sin(state[1])*cos(state[0])*cos(state[2]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*cos(state[2]) - sin(state[2])*cos(state[0]))*sin(dt*state[8])*cos(dt*state[7]) + cos(dt*state[7])*cos(dt*state[8])*cos(state[1])*cos(state[2]), 2) + pow(-(-sin(state[0])*cos(state[2]) + sin(state[1])*sin(state[2])*cos(state[0]))*sin(dt*state[7]) + (sin(state[0])*sin(state[1])*sin(state[2]) + cos(state[0])*cos(state[2]))*sin(dt*state[8])*cos(dt*state[7]) + sin(state[2])*cos(dt*state[7])*cos(dt*state[8])*cos(state[1]), 2));
   out_1397960411052043499[45] = 0;
   out_1397960411052043499[46] = 0;
   out_1397960411052043499[47] = 0;
   out_1397960411052043499[48] = 0;
   out_1397960411052043499[49] = 0;
   out_1397960411052043499[50] = 0;
   out_1397960411052043499[51] = 0;
   out_1397960411052043499[52] = 0;
   out_1397960411052043499[53] = 0;
   out_1397960411052043499[54] = 0;
   out_1397960411052043499[55] = 0;
   out_1397960411052043499[56] = 0;
   out_1397960411052043499[57] = 1;
   out_1397960411052043499[58] = 0;
   out_1397960411052043499[59] = 0;
   out_1397960411052043499[60] = 0;
   out_1397960411052043499[61] = 0;
   out_1397960411052043499[62] = 0;
   out_1397960411052043499[63] = 0;
   out_1397960411052043499[64] = 0;
   out_1397960411052043499[65] = 0;
   out_1397960411052043499[66] = dt;
   out_1397960411052043499[67] = 0;
   out_1397960411052043499[68] = 0;
   out_1397960411052043499[69] = 0;
   out_1397960411052043499[70] = 0;
   out_1397960411052043499[71] = 0;
   out_1397960411052043499[72] = 0;
   out_1397960411052043499[73] = 0;
   out_1397960411052043499[74] = 0;
   out_1397960411052043499[75] = 0;
   out_1397960411052043499[76] = 1;
   out_1397960411052043499[77] = 0;
   out_1397960411052043499[78] = 0;
   out_1397960411052043499[79] = 0;
   out_1397960411052043499[80] = 0;
   out_1397960411052043499[81] = 0;
   out_1397960411052043499[82] = 0;
   out_1397960411052043499[83] = 0;
   out_1397960411052043499[84] = 0;
   out_1397960411052043499[85] = dt;
   out_1397960411052043499[86] = 0;
   out_1397960411052043499[87] = 0;
   out_1397960411052043499[88] = 0;
   out_1397960411052043499[89] = 0;
   out_1397960411052043499[90] = 0;
   out_1397960411052043499[91] = 0;
   out_1397960411052043499[92] = 0;
   out_1397960411052043499[93] = 0;
   out_1397960411052043499[94] = 0;
   out_1397960411052043499[95] = 1;
   out_1397960411052043499[96] = 0;
   out_1397960411052043499[97] = 0;
   out_1397960411052043499[98] = 0;
   out_1397960411052043499[99] = 0;
   out_1397960411052043499[100] = 0;
   out_1397960411052043499[101] = 0;
   out_1397960411052043499[102] = 0;
   out_1397960411052043499[103] = 0;
   out_1397960411052043499[104] = dt;
   out_1397960411052043499[105] = 0;
   out_1397960411052043499[106] = 0;
   out_1397960411052043499[107] = 0;
   out_1397960411052043499[108] = 0;
   out_1397960411052043499[109] = 0;
   out_1397960411052043499[110] = 0;
   out_1397960411052043499[111] = 0;
   out_1397960411052043499[112] = 0;
   out_1397960411052043499[113] = 0;
   out_1397960411052043499[114] = 1;
   out_1397960411052043499[115] = 0;
   out_1397960411052043499[116] = 0;
   out_1397960411052043499[117] = 0;
   out_1397960411052043499[118] = 0;
   out_1397960411052043499[119] = 0;
   out_1397960411052043499[120] = 0;
   out_1397960411052043499[121] = 0;
   out_1397960411052043499[122] = 0;
   out_1397960411052043499[123] = 0;
   out_1397960411052043499[124] = 0;
   out_1397960411052043499[125] = 0;
   out_1397960411052043499[126] = 0;
   out_1397960411052043499[127] = 0;
   out_1397960411052043499[128] = 0;
   out_1397960411052043499[129] = 0;
   out_1397960411052043499[130] = 0;
   out_1397960411052043499[131] = 0;
   out_1397960411052043499[132] = 0;
   out_1397960411052043499[133] = 1;
   out_1397960411052043499[134] = 0;
   out_1397960411052043499[135] = 0;
   out_1397960411052043499[136] = 0;
   out_1397960411052043499[137] = 0;
   out_1397960411052043499[138] = 0;
   out_1397960411052043499[139] = 0;
   out_1397960411052043499[140] = 0;
   out_1397960411052043499[141] = 0;
   out_1397960411052043499[142] = 0;
   out_1397960411052043499[143] = 0;
   out_1397960411052043499[144] = 0;
   out_1397960411052043499[145] = 0;
   out_1397960411052043499[146] = 0;
   out_1397960411052043499[147] = 0;
   out_1397960411052043499[148] = 0;
   out_1397960411052043499[149] = 0;
   out_1397960411052043499[150] = 0;
   out_1397960411052043499[151] = 0;
   out_1397960411052043499[152] = 1;
   out_1397960411052043499[153] = 0;
   out_1397960411052043499[154] = 0;
   out_1397960411052043499[155] = 0;
   out_1397960411052043499[156] = 0;
   out_1397960411052043499[157] = 0;
   out_1397960411052043499[158] = 0;
   out_1397960411052043499[159] = 0;
   out_1397960411052043499[160] = 0;
   out_1397960411052043499[161] = 0;
   out_1397960411052043499[162] = 0;
   out_1397960411052043499[163] = 0;
   out_1397960411052043499[164] = 0;
   out_1397960411052043499[165] = 0;
   out_1397960411052043499[166] = 0;
   out_1397960411052043499[167] = 0;
   out_1397960411052043499[168] = 0;
   out_1397960411052043499[169] = 0;
   out_1397960411052043499[170] = 0;
   out_1397960411052043499[171] = 1;
   out_1397960411052043499[172] = 0;
   out_1397960411052043499[173] = 0;
   out_1397960411052043499[174] = 0;
   out_1397960411052043499[175] = 0;
   out_1397960411052043499[176] = 0;
   out_1397960411052043499[177] = 0;
   out_1397960411052043499[178] = 0;
   out_1397960411052043499[179] = 0;
   out_1397960411052043499[180] = 0;
   out_1397960411052043499[181] = 0;
   out_1397960411052043499[182] = 0;
   out_1397960411052043499[183] = 0;
   out_1397960411052043499[184] = 0;
   out_1397960411052043499[185] = 0;
   out_1397960411052043499[186] = 0;
   out_1397960411052043499[187] = 0;
   out_1397960411052043499[188] = 0;
   out_1397960411052043499[189] = 0;
   out_1397960411052043499[190] = 1;
   out_1397960411052043499[191] = 0;
   out_1397960411052043499[192] = 0;
   out_1397960411052043499[193] = 0;
   out_1397960411052043499[194] = 0;
   out_1397960411052043499[195] = 0;
   out_1397960411052043499[196] = 0;
   out_1397960411052043499[197] = 0;
   out_1397960411052043499[198] = 0;
   out_1397960411052043499[199] = 0;
   out_1397960411052043499[200] = 0;
   out_1397960411052043499[201] = 0;
   out_1397960411052043499[202] = 0;
   out_1397960411052043499[203] = 0;
   out_1397960411052043499[204] = 0;
   out_1397960411052043499[205] = 0;
   out_1397960411052043499[206] = 0;
   out_1397960411052043499[207] = 0;
   out_1397960411052043499[208] = 0;
   out_1397960411052043499[209] = 1;
   out_1397960411052043499[210] = 0;
   out_1397960411052043499[211] = 0;
   out_1397960411052043499[212] = 0;
   out_1397960411052043499[213] = 0;
   out_1397960411052043499[214] = 0;
   out_1397960411052043499[215] = 0;
   out_1397960411052043499[216] = 0;
   out_1397960411052043499[217] = 0;
   out_1397960411052043499[218] = 0;
   out_1397960411052043499[219] = 0;
   out_1397960411052043499[220] = 0;
   out_1397960411052043499[221] = 0;
   out_1397960411052043499[222] = 0;
   out_1397960411052043499[223] = 0;
   out_1397960411052043499[224] = 0;
   out_1397960411052043499[225] = 0;
   out_1397960411052043499[226] = 0;
   out_1397960411052043499[227] = 0;
   out_1397960411052043499[228] = 1;
   out_1397960411052043499[229] = 0;
   out_1397960411052043499[230] = 0;
   out_1397960411052043499[231] = 0;
   out_1397960411052043499[232] = 0;
   out_1397960411052043499[233] = 0;
   out_1397960411052043499[234] = 0;
   out_1397960411052043499[235] = 0;
   out_1397960411052043499[236] = 0;
   out_1397960411052043499[237] = 0;
   out_1397960411052043499[238] = 0;
   out_1397960411052043499[239] = 0;
   out_1397960411052043499[240] = 0;
   out_1397960411052043499[241] = 0;
   out_1397960411052043499[242] = 0;
   out_1397960411052043499[243] = 0;
   out_1397960411052043499[244] = 0;
   out_1397960411052043499[245] = 0;
   out_1397960411052043499[246] = 0;
   out_1397960411052043499[247] = 1;
   out_1397960411052043499[248] = 0;
   out_1397960411052043499[249] = 0;
   out_1397960411052043499[250] = 0;
   out_1397960411052043499[251] = 0;
   out_1397960411052043499[252] = 0;
   out_1397960411052043499[253] = 0;
   out_1397960411052043499[254] = 0;
   out_1397960411052043499[255] = 0;
   out_1397960411052043499[256] = 0;
   out_1397960411052043499[257] = 0;
   out_1397960411052043499[258] = 0;
   out_1397960411052043499[259] = 0;
   out_1397960411052043499[260] = 0;
   out_1397960411052043499[261] = 0;
   out_1397960411052043499[262] = 0;
   out_1397960411052043499[263] = 0;
   out_1397960411052043499[264] = 0;
   out_1397960411052043499[265] = 0;
   out_1397960411052043499[266] = 1;
   out_1397960411052043499[267] = 0;
   out_1397960411052043499[268] = 0;
   out_1397960411052043499[269] = 0;
   out_1397960411052043499[270] = 0;
   out_1397960411052043499[271] = 0;
   out_1397960411052043499[272] = 0;
   out_1397960411052043499[273] = 0;
   out_1397960411052043499[274] = 0;
   out_1397960411052043499[275] = 0;
   out_1397960411052043499[276] = 0;
   out_1397960411052043499[277] = 0;
   out_1397960411052043499[278] = 0;
   out_1397960411052043499[279] = 0;
   out_1397960411052043499[280] = 0;
   out_1397960411052043499[281] = 0;
   out_1397960411052043499[282] = 0;
   out_1397960411052043499[283] = 0;
   out_1397960411052043499[284] = 0;
   out_1397960411052043499[285] = 1;
   out_1397960411052043499[286] = 0;
   out_1397960411052043499[287] = 0;
   out_1397960411052043499[288] = 0;
   out_1397960411052043499[289] = 0;
   out_1397960411052043499[290] = 0;
   out_1397960411052043499[291] = 0;
   out_1397960411052043499[292] = 0;
   out_1397960411052043499[293] = 0;
   out_1397960411052043499[294] = 0;
   out_1397960411052043499[295] = 0;
   out_1397960411052043499[296] = 0;
   out_1397960411052043499[297] = 0;
   out_1397960411052043499[298] = 0;
   out_1397960411052043499[299] = 0;
   out_1397960411052043499[300] = 0;
   out_1397960411052043499[301] = 0;
   out_1397960411052043499[302] = 0;
   out_1397960411052043499[303] = 0;
   out_1397960411052043499[304] = 1;
   out_1397960411052043499[305] = 0;
   out_1397960411052043499[306] = 0;
   out_1397960411052043499[307] = 0;
   out_1397960411052043499[308] = 0;
   out_1397960411052043499[309] = 0;
   out_1397960411052043499[310] = 0;
   out_1397960411052043499[311] = 0;
   out_1397960411052043499[312] = 0;
   out_1397960411052043499[313] = 0;
   out_1397960411052043499[314] = 0;
   out_1397960411052043499[315] = 0;
   out_1397960411052043499[316] = 0;
   out_1397960411052043499[317] = 0;
   out_1397960411052043499[318] = 0;
   out_1397960411052043499[319] = 0;
   out_1397960411052043499[320] = 0;
   out_1397960411052043499[321] = 0;
   out_1397960411052043499[322] = 0;
   out_1397960411052043499[323] = 1;
}
void h_4(double *state, double *unused, double *out_111977664207872713) {
   out_111977664207872713[0] = state[6] + state[9];
   out_111977664207872713[1] = state[7] + state[10];
   out_111977664207872713[2] = state[8] + state[11];
}
void H_4(double *state, double *unused, double *out_2462081651858261163) {
   out_2462081651858261163[0] = 0;
   out_2462081651858261163[1] = 0;
   out_2462081651858261163[2] = 0;
   out_2462081651858261163[3] = 0;
   out_2462081651858261163[4] = 0;
   out_2462081651858261163[5] = 0;
   out_2462081651858261163[6] = 1;
   out_2462081651858261163[7] = 0;
   out_2462081651858261163[8] = 0;
   out_2462081651858261163[9] = 1;
   out_2462081651858261163[10] = 0;
   out_2462081651858261163[11] = 0;
   out_2462081651858261163[12] = 0;
   out_2462081651858261163[13] = 0;
   out_2462081651858261163[14] = 0;
   out_2462081651858261163[15] = 0;
   out_2462081651858261163[16] = 0;
   out_2462081651858261163[17] = 0;
   out_2462081651858261163[18] = 0;
   out_2462081651858261163[19] = 0;
   out_2462081651858261163[20] = 0;
   out_2462081651858261163[21] = 0;
   out_2462081651858261163[22] = 0;
   out_2462081651858261163[23] = 0;
   out_2462081651858261163[24] = 0;
   out_2462081651858261163[25] = 1;
   out_2462081651858261163[26] = 0;
   out_2462081651858261163[27] = 0;
   out_2462081651858261163[28] = 1;
   out_2462081651858261163[29] = 0;
   out_2462081651858261163[30] = 0;
   out_2462081651858261163[31] = 0;
   out_2462081651858261163[32] = 0;
   out_2462081651858261163[33] = 0;
   out_2462081651858261163[34] = 0;
   out_2462081651858261163[35] = 0;
   out_2462081651858261163[36] = 0;
   out_2462081651858261163[37] = 0;
   out_2462081651858261163[38] = 0;
   out_2462081651858261163[39] = 0;
   out_2462081651858261163[40] = 0;
   out_2462081651858261163[41] = 0;
   out_2462081651858261163[42] = 0;
   out_2462081651858261163[43] = 0;
   out_2462081651858261163[44] = 1;
   out_2462081651858261163[45] = 0;
   out_2462081651858261163[46] = 0;
   out_2462081651858261163[47] = 1;
   out_2462081651858261163[48] = 0;
   out_2462081651858261163[49] = 0;
   out_2462081651858261163[50] = 0;
   out_2462081651858261163[51] = 0;
   out_2462081651858261163[52] = 0;
   out_2462081651858261163[53] = 0;
}
void h_10(double *state, double *unused, double *out_1198457513949802947) {
   out_1198457513949802947[0] = 9.8100000000000005*sin(state[1]) - state[4]*state[8] + state[5]*state[7] + state[12] + state[15];
   out_1198457513949802947[1] = -9.8100000000000005*sin(state[0])*cos(state[1]) + state[3]*state[8] - state[5]*state[6] + state[13] + state[16];
   out_1198457513949802947[2] = -9.8100000000000005*cos(state[0])*cos(state[1]) - state[3]*state[7] + state[4]*state[6] + state[14] + state[17];
}
void H_10(double *state, double *unused, double *out_5637433044053919992) {
   out_5637433044053919992[0] = 0;
   out_5637433044053919992[1] = 9.8100000000000005*cos(state[1]);
   out_5637433044053919992[2] = 0;
   out_5637433044053919992[3] = 0;
   out_5637433044053919992[4] = -state[8];
   out_5637433044053919992[5] = state[7];
   out_5637433044053919992[6] = 0;
   out_5637433044053919992[7] = state[5];
   out_5637433044053919992[8] = -state[4];
   out_5637433044053919992[9] = 0;
   out_5637433044053919992[10] = 0;
   out_5637433044053919992[11] = 0;
   out_5637433044053919992[12] = 1;
   out_5637433044053919992[13] = 0;
   out_5637433044053919992[14] = 0;
   out_5637433044053919992[15] = 1;
   out_5637433044053919992[16] = 0;
   out_5637433044053919992[17] = 0;
   out_5637433044053919992[18] = -9.8100000000000005*cos(state[0])*cos(state[1]);
   out_5637433044053919992[19] = 9.8100000000000005*sin(state[0])*sin(state[1]);
   out_5637433044053919992[20] = 0;
   out_5637433044053919992[21] = state[8];
   out_5637433044053919992[22] = 0;
   out_5637433044053919992[23] = -state[6];
   out_5637433044053919992[24] = -state[5];
   out_5637433044053919992[25] = 0;
   out_5637433044053919992[26] = state[3];
   out_5637433044053919992[27] = 0;
   out_5637433044053919992[28] = 0;
   out_5637433044053919992[29] = 0;
   out_5637433044053919992[30] = 0;
   out_5637433044053919992[31] = 1;
   out_5637433044053919992[32] = 0;
   out_5637433044053919992[33] = 0;
   out_5637433044053919992[34] = 1;
   out_5637433044053919992[35] = 0;
   out_5637433044053919992[36] = 9.8100000000000005*sin(state[0])*cos(state[1]);
   out_5637433044053919992[37] = 9.8100000000000005*sin(state[1])*cos(state[0]);
   out_5637433044053919992[38] = 0;
   out_5637433044053919992[39] = -state[7];
   out_5637433044053919992[40] = state[6];
   out_5637433044053919992[41] = 0;
   out_5637433044053919992[42] = state[4];
   out_5637433044053919992[43] = -state[3];
   out_5637433044053919992[44] = 0;
   out_5637433044053919992[45] = 0;
   out_5637433044053919992[46] = 0;
   out_5637433044053919992[47] = 0;
   out_5637433044053919992[48] = 0;
   out_5637433044053919992[49] = 0;
   out_5637433044053919992[50] = 1;
   out_5637433044053919992[51] = 0;
   out_5637433044053919992[52] = 0;
   out_5637433044053919992[53] = 1;
}
void h_13(double *state, double *unused, double *out_6919936230217658492) {
   out_6919936230217658492[0] = state[3];
   out_6919936230217658492[1] = state[4];
   out_6919936230217658492[2] = state[5];
}
void H_13(double *state, double *unused, double *out_5674355477190593964) {
   out_5674355477190593964[0] = 0;
   out_5674355477190593964[1] = 0;
   out_5674355477190593964[2] = 0;
   out_5674355477190593964[3] = 1;
   out_5674355477190593964[4] = 0;
   out_5674355477190593964[5] = 0;
   out_5674355477190593964[6] = 0;
   out_5674355477190593964[7] = 0;
   out_5674355477190593964[8] = 0;
   out_5674355477190593964[9] = 0;
   out_5674355477190593964[10] = 0;
   out_5674355477190593964[11] = 0;
   out_5674355477190593964[12] = 0;
   out_5674355477190593964[13] = 0;
   out_5674355477190593964[14] = 0;
   out_5674355477190593964[15] = 0;
   out_5674355477190593964[16] = 0;
   out_5674355477190593964[17] = 0;
   out_5674355477190593964[18] = 0;
   out_5674355477190593964[19] = 0;
   out_5674355477190593964[20] = 0;
   out_5674355477190593964[21] = 0;
   out_5674355477190593964[22] = 1;
   out_5674355477190593964[23] = 0;
   out_5674355477190593964[24] = 0;
   out_5674355477190593964[25] = 0;
   out_5674355477190593964[26] = 0;
   out_5674355477190593964[27] = 0;
   out_5674355477190593964[28] = 0;
   out_5674355477190593964[29] = 0;
   out_5674355477190593964[30] = 0;
   out_5674355477190593964[31] = 0;
   out_5674355477190593964[32] = 0;
   out_5674355477190593964[33] = 0;
   out_5674355477190593964[34] = 0;
   out_5674355477190593964[35] = 0;
   out_5674355477190593964[36] = 0;
   out_5674355477190593964[37] = 0;
   out_5674355477190593964[38] = 0;
   out_5674355477190593964[39] = 0;
   out_5674355477190593964[40] = 0;
   out_5674355477190593964[41] = 1;
   out_5674355477190593964[42] = 0;
   out_5674355477190593964[43] = 0;
   out_5674355477190593964[44] = 0;
   out_5674355477190593964[45] = 0;
   out_5674355477190593964[46] = 0;
   out_5674355477190593964[47] = 0;
   out_5674355477190593964[48] = 0;
   out_5674355477190593964[49] = 0;
   out_5674355477190593964[50] = 0;
   out_5674355477190593964[51] = 0;
   out_5674355477190593964[52] = 0;
   out_5674355477190593964[53] = 0;
}
void h_14(double *state, double *unused, double *out_6919825385847265547) {
   out_6919825385847265547[0] = state[6];
   out_6919825385847265547[1] = state[7];
   out_6919825385847265547[2] = state[8];
}
void H_14(double *state, double *unused, double *out_6425322508197745692) {
   out_6425322508197745692[0] = 0;
   out_6425322508197745692[1] = 0;
   out_6425322508197745692[2] = 0;
   out_6425322508197745692[3] = 0;
   out_6425322508197745692[4] = 0;
   out_6425322508197745692[5] = 0;
   out_6425322508197745692[6] = 1;
   out_6425322508197745692[7] = 0;
   out_6425322508197745692[8] = 0;
   out_6425322508197745692[9] = 0;
   out_6425322508197745692[10] = 0;
   out_6425322508197745692[11] = 0;
   out_6425322508197745692[12] = 0;
   out_6425322508197745692[13] = 0;
   out_6425322508197745692[14] = 0;
   out_6425322508197745692[15] = 0;
   out_6425322508197745692[16] = 0;
   out_6425322508197745692[17] = 0;
   out_6425322508197745692[18] = 0;
   out_6425322508197745692[19] = 0;
   out_6425322508197745692[20] = 0;
   out_6425322508197745692[21] = 0;
   out_6425322508197745692[22] = 0;
   out_6425322508197745692[23] = 0;
   out_6425322508197745692[24] = 0;
   out_6425322508197745692[25] = 1;
   out_6425322508197745692[26] = 0;
   out_6425322508197745692[27] = 0;
   out_6425322508197745692[28] = 0;
   out_6425322508197745692[29] = 0;
   out_6425322508197745692[30] = 0;
   out_6425322508197745692[31] = 0;
   out_6425322508197745692[32] = 0;
   out_6425322508197745692[33] = 0;
   out_6425322508197745692[34] = 0;
   out_6425322508197745692[35] = 0;
   out_6425322508197745692[36] = 0;
   out_6425322508197745692[37] = 0;
   out_6425322508197745692[38] = 0;
   out_6425322508197745692[39] = 0;
   out_6425322508197745692[40] = 0;
   out_6425322508197745692[41] = 0;
   out_6425322508197745692[42] = 0;
   out_6425322508197745692[43] = 0;
   out_6425322508197745692[44] = 1;
   out_6425322508197745692[45] = 0;
   out_6425322508197745692[46] = 0;
   out_6425322508197745692[47] = 0;
   out_6425322508197745692[48] = 0;
   out_6425322508197745692[49] = 0;
   out_6425322508197745692[50] = 0;
   out_6425322508197745692[51] = 0;
   out_6425322508197745692[52] = 0;
   out_6425322508197745692[53] = 0;
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

void pose_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_4, H_4, NULL, in_z, in_R, in_ea, MAHA_THRESH_4);
}
void pose_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_10, H_10, NULL, in_z, in_R, in_ea, MAHA_THRESH_10);
}
void pose_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_13, H_13, NULL, in_z, in_R, in_ea, MAHA_THRESH_13);
}
void pose_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea) {
  update<3, 3, 0>(in_x, in_P, h_14, H_14, NULL, in_z, in_R, in_ea, MAHA_THRESH_14);
}
void pose_err_fun(double *nom_x, double *delta_x, double *out_675686294106479216) {
  err_fun(nom_x, delta_x, out_675686294106479216);
}
void pose_inv_err_fun(double *nom_x, double *true_x, double *out_1402524249024729268) {
  inv_err_fun(nom_x, true_x, out_1402524249024729268);
}
void pose_H_mod_fun(double *state, double *out_6550902768055423329) {
  H_mod_fun(state, out_6550902768055423329);
}
void pose_f_fun(double *state, double dt, double *out_3370286758101883761) {
  f_fun(state,  dt, out_3370286758101883761);
}
void pose_F_fun(double *state, double dt, double *out_1397960411052043499) {
  F_fun(state,  dt, out_1397960411052043499);
}
void pose_h_4(double *state, double *unused, double *out_111977664207872713) {
  h_4(state, unused, out_111977664207872713);
}
void pose_H_4(double *state, double *unused, double *out_2462081651858261163) {
  H_4(state, unused, out_2462081651858261163);
}
void pose_h_10(double *state, double *unused, double *out_1198457513949802947) {
  h_10(state, unused, out_1198457513949802947);
}
void pose_H_10(double *state, double *unused, double *out_5637433044053919992) {
  H_10(state, unused, out_5637433044053919992);
}
void pose_h_13(double *state, double *unused, double *out_6919936230217658492) {
  h_13(state, unused, out_6919936230217658492);
}
void pose_H_13(double *state, double *unused, double *out_5674355477190593964) {
  H_13(state, unused, out_5674355477190593964);
}
void pose_h_14(double *state, double *unused, double *out_6919825385847265547) {
  h_14(state, unused, out_6919825385847265547);
}
void pose_H_14(double *state, double *unused, double *out_6425322508197745692) {
  H_14(state, unused, out_6425322508197745692);
}
void pose_predict(double *in_x, double *in_P, double *in_Q, double dt) {
  predict(in_x, in_P, in_Q, dt);
}
}

const EKF pose = {
  .name = "pose",
  .kinds = { 4, 10, 13, 14 },
  .feature_kinds = {  },
  .f_fun = pose_f_fun,
  .F_fun = pose_F_fun,
  .err_fun = pose_err_fun,
  .inv_err_fun = pose_inv_err_fun,
  .H_mod_fun = pose_H_mod_fun,
  .predict = pose_predict,
  .hs = {
    { 4, pose_h_4 },
    { 10, pose_h_10 },
    { 13, pose_h_13 },
    { 14, pose_h_14 },
  },
  .Hs = {
    { 4, pose_H_4 },
    { 10, pose_H_10 },
    { 13, pose_H_13 },
    { 14, pose_H_14 },
  },
  .updates = {
    { 4, pose_update_4 },
    { 10, pose_update_10 },
    { 13, pose_update_13 },
    { 14, pose_update_14 },
  },
  .Hes = {
  },
  .sets = {
  },
  .extra_routines = {
  },
};

ekf_lib_init(pose)
