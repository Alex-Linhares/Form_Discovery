function [Y, dY] = l0b_hessfun(X, A, b, shape)
% Helper for fx_l0b.m (hessiangrad): a smooth non-quadratic function with gradient.
% dY is reshaped to SHAPE (row or column; hessiangrad applies vec). Mirrored in
% tests/test_l0b.py::hessfun.
Y = 0.5 * X' * A * X + b' * X + sum(sin(X)) + 0.25 * sum(X .^ 4);
g = A * X + b + cos(X) + X .^ 3;
dY = reshape(g, shape);
