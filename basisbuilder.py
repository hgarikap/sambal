#! /usr/bin/env python


from nutils import topology, element, function, plot, util, mesh
import numpy


class BasisBuilder( object ):

  def __init__( self, ndims ):
    self.ndims = ndims

  def __mul__( self, other ):
    return ProductFunc( self, other )

  def build( self, topo ):
    assert isinstance( topo, topology.StructuredTopology )
    assert topo.ndims == self.ndims

    dofshape = self.getdofshape( topo.structure.shape )
    slices = self.getslices( topo.structure.shape )
    stdelems = self.getstdelems( topo.structure.shape )

    ndofs = numpy.product(dofshape)
    dofs = numpy.arange( ndofs ).reshape( dofshape )
    idx = numpy.frompyfunc( lambda *s: dofs[s].ravel(), len(slices), 1 )( *numpy.ix_( *slices ) )
    return function.function(
      fmap = { elem.transform: ((funcs,None),) for elem, funcs in numpy.broadcast( topo.structure, stdelems ) },
      nmap = { elem.transform: dofs for elem, dofs in numpy.broadcast( topo.structure, idx ) },
      ndofs = ndofs,
      ndims = topo.ndims )


class ProductFunc( BasisBuilder ):

  def __init__( self, func1, func2 ):
    assert isinstance( func1, BasisBuilder )
    assert isinstance( func2, BasisBuilder )
    self.func1 = func1
    self.func2 = func2
    BasisBuilder.__init__( self, ndims=func1.ndims+func2.ndims )

  def getdofshape( self, shape ):
    assert len(shape) == self.ndims
    return self.func1.getdofshape( shape[:self.func1.ndims] ) \
         + self.func2.getdofshape( shape[self.func1.ndims:] )

  def getslices( self, shape ):
    assert len(shape) == self.ndims
    return self.func1.getslices( shape[:self.func1.ndims] ) \
         + self.func2.getslices( shape[self.func1.ndims:] )

  def getstdelems( self, shape ):
    assert len(shape) == self.ndims
    return self.func1.getstdelems( shape[:self.func1.ndims] )[(Ellipsis,)+(numpy.newaxis,)*self.func2.ndims] \
         * self.func2.getstdelems( shape[self.func1.ndims:] )


class Spline( BasisBuilder ):

  def __init__( self, degree, rmfirst=False, rmlast=False ):
    self.degree = degree
    self.rmfirst = rmfirst
    self.rmlast = rmlast
    BasisBuilder.__init__( self, ndims=1 )

  def getdofshape( self, (nelems,) ):
    return nelems + self.degree - self.rmfirst - self.rmlast,

  def getslices( self, (nelems,) ):
    N, = self.getdofshape( [nelems] )
    return [[ slice(max(0,i),min(N,i+self.degree+1)) for i in numpy.arange(nelems)-self.rmfirst ]]

  def getstdelems( self, (nelems,) ):
    stdelems = element.PolyLine.spline( degree=self.degree, nelems=nelems )
    if self.rmfirst:
      stdelems[0] = stdelems[0].extract( numpy.eye(stdelems[0].nshapes)[:,1:] )
    if self.rmlast:
      stdelems[-1] = stdelems[-1].extract( numpy.eye(stdelems[-1].nshapes)[:,:-1] )
    return stdelems
    

class ModSpline2( BasisBuilder ):

  def __init__( self, ifaces, rmfirst=False, rmlast=False ):
    self.ifaces = tuple(ifaces)
    self.rmfirst = rmfirst
    self.rmlast = rmlast
    BasisBuilder.__init__( self, ndims=1 )

  def sorted_ifaces( self, nelems ):
    ifaces = numpy.sort([ nelems+iface if iface < 0 else iface for iface in self.ifaces ])
    assert ifaces[0] >= 2 and numpy.all( numpy.diff(ifaces) >= 4 ) and ifaces[-1] <= nelems-2
    return ifaces

  def getdofshape( self, (nelems,) ):
    return nelems + 2 - self.rmfirst - self.rmlast,

  def getslices( self, (nelems,) ):
    N, = self.getdofshape( [nelems] )
    slices = [ slice(max(0,i),min(N,i+3)) for i in numpy.arange(nelems)-self.rmfirst ]
    for n in self.sorted_ifaces( nelems ):
      i = n - self.rmfirst
      slices[n-2] = slice(max(0,i-2),i+2)
      slices[n+1] = slice(i,min(N,i+4))
    return [ slices ]

  def getstdelems( self, (nelems,) ):
    stdelems = element.PolyLine.spline( degree=2, nelems=nelems )
    for n in self.sorted_ifaces( nelems ):
      stdelems[n-2] = stdelems[n-2].extract( [[1,0,0,0],[0,1,0,0],[0,0,1,1]] )
      stdelems[n-1] = stdelems[n-1].extract( [[1,0,0],[0,1,1],[0,-1,1]] )
      stdelems[n+0] = stdelems[n+0].extract( [[1,1,0],[-1,1,0],[0,0,1]] )
      stdelems[n+1] = stdelems[n+1].extract( [[-1,1,0,0],[0,0,1,0],[0,0,0,1]] )
    if self.rmfirst:
      stdelems[0] = stdelems[0].extract( numpy.eye(stdelems[0].nshapes)[:,1:] )
    if self.rmlast:
      stdelems[-1] = stdelems[-1].extract( numpy.eye(stdelems[-1].nshapes)[:,:-1] )
    return stdelems


def example():

  verts = numpy.arange(10)
  domain, geom = mesh.rectilinear( [ verts ] )
  basis = ModSpline2( [2,-3], rmlast=True ).build(domain)
  x, y = domain.elem_eval( [ geom[0], basis ], ischeme='bezier9' )
  with plot.PyPlot( '1D' ) as plt:
    plt.plot( x, y, '-' )

  domain, geom = mesh.rectilinear( [ numpy.arange(5) ] * 2 )
  basis = ( Spline(1,rmfirst=True) * ModSpline2( [2] ) ).build(domain)
  x, y = domain.elem_eval( [ geom, basis ], ischeme='bezier5' )
  with plot.PyPlot( '1D' ) as plt:
    for i, yi in enumerate( y.T ):
      plt.subplot( 4, 6, i+1 )
      plt.mesh( x, yi )
      plt.gca().set_axis_off()


if __name__ == '__main__':
  util.run( example )
