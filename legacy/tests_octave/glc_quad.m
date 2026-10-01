function [f, g] = glc_quad(x, A, b, ps)
% Quadratic test objective for fx_glslow.m's Laplace cases: f = x'*A*x/2 - b'*x,
% called as feval(dprobfun, x, data, graphL, ps) with data = A, graphL = b.
f = x' * A * x / 2 - b' * x;
g = A * x - b;
end
