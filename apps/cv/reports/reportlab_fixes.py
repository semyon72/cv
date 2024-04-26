# IDE: PyCharm
# Project: cv
# Path: apps/cv/reports
# File: reportlab_fixes.py
# Contact: Semyon Mamonov <semyon.mamonov@gmail.com>
# Created by ox23 at 2023-12-12 (y-m-d) 2:49 PM

from reportlab import rl_config

if rl_config.shapeChecking:
    print('''WARNING:
        Current state of rl_config.shapeChecking == True
        For optimisation, put on fist line  
        >>> from reportlab import rl_config
        >>> rl_config.shapeChecking = False
        It will grow the throughput 2 times at least  
    ''')

from reportlab.graphics.shapes import Drawing

from reportlab.platypus.flowables import (
    Flowable, BalancedColumns, Preformatted,
    _ExtendBG, _AbsRect, _AbsLine, KeepInFrame, PageBreak, _FindSplitterMixin, cdeepcopy
)


class _FindSplitterMixin(_FindSplitterMixin):
    float_correction = 1e-6

    def _findSplit(self,canv,availWidth,availHeight,mergeSpace=1,obj=None,content=None,paraFix=True):
        '''return max width, required height for a list of flowables F'''
        W = 0
        H = 0
        pS = sB = 0
        atTop = 1
        F = self._getContent(content)
        for i,f in enumerate(F):
            if hasattr(f,'frameAction'):
                from reportlab.platypus.doctemplate import Indenter
                if isinstance(f,Indenter):
                    availWidth -= f.left+f.right
                continue
            w,h = f.wrapOn(canv,availWidth,0xfffffff)
            if w<=rl_config._FUZZ or h<=rl_config._FUZZ: continue
            W = max(W,w)
            if not atTop:
                s = f.getSpaceBefore()
                if mergeSpace: s = max(s-pS,0)
                H += s
            else:
                if obj is not None: obj._spaceBefore = f.getSpaceBefore()
                atTop = 0
            if H>=availHeight or w - availWidth > self.float_correction:
                return W, availHeight, F[:i],F[i:]
            H += h
            if H>availHeight:
                aH = availHeight-(H-h)
                if paraFix:
                    from reportlab.platypus.paragraph import Paragraph
                    if isinstance(f,(Paragraph,Preformatted)):
                        leading = f.style.leading
                        nH = leading*int(aH/float(leading))+rl_config._FUZZ
                        if nH<aH: nH += leading
                        availHeight += nH-aH
                        aH = nH
                try:
                    S = cdeepcopy(f).splitOn(canv,availWidth,aH)
                except:
                    S  = None   #sometimes the deepcopy cannot be done
                if not S:
                    return W, availHeight, F[:i],F[i:]
                else:
                    return W,availHeight,F[:i]+S[:1],S[1:]+F[i+1:]
            pS = f.getSpaceAfter()
            H += pS

        if obj is not None: obj._spaceAfter = pS
        return W, H-pS, F, []


class BalancedColumns(_FindSplitterMixin, BalancedColumns):
    """
        1. if no-ones Flowable do not split and to fit for rest height
        Fix - for errror ->
        Fix lines :
            (+-) ~174: if C[0]==[] and C[1]==[] and C1:
            (+-) ~194: if no_split:
            (+) ~58:
            (+-) ~319: G.append(self._create_next(C1))
        ...
        File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/platypus/flowables.py", line 1785, in wrap
         H1, G = self._generated_content(aW,aH)
        File "/home/ox23/Python.projects/cv/workroom/reportlab/charts_in_balanced_column_with_legend.py", line 266, in _generated_content
         Ci = C[i]
        IndexError: list index out of range

        Old source
            #no split situation
            C, C1 = [C1,C[1]], C[0]

    """

    def _create_next(self, C1):
        return self.__class__(
            C1,
            nCols=self._nCols,
            needed=self._needed, spaceBefore=self.spaceBefore, spaceAfter=self.spaceAfter,
            showBoundary=self.showBoundary, leftPadding=self._leftPadding, innerPadding=self._innerPadding,
            rightPadding=self._rightPadding, topPadding=self._topPadding, bottomPadding=self._bottomPadding,
            name=self.name + '-1', endSlack=self.endSlack, boxStrokeColor=self._boxStrokeColor,
            boxStrokeWidth=self._boxStrokeWidth, boxFillColor=self._boxFillColor, boxMargin=self._boxMargin,
            vLinesStrokeColor=self._vLinesStrokeColor, vLinesStrokeWidth=self._vLinesStrokeWidth,
        )

    def _generated_content(self,aW,aH):
        G = []
        frame = self._frame
        from reportlab.platypus.doctemplate import LayoutError, ActionFlowable, Indenter
        from reportlab.platypus.frames import Frame
        from reportlab.platypus.doctemplate import FrameBreak
        lpad = frame._leftPadding if self._leftPadding is None else self._leftPadding
        rpad = frame._rightPadding if self._rightPadding is None else self._rightPadding
        tpad = frame._topPadding if self._topPadding is None else self._topPadding
        bpad = frame._bottomPadding if self._bottomPadding is None else self._bottomPadding
        leftExtraIndent = frame._leftExtraIndent
        rightExtraIndent = frame._rightExtraIndent
        gap = max(lpad,rpad) if self._innerPadding is None else self._innerPadding
        hgap = gap*0.5
        canv = self.canv
        nCols = self._nCols
        cw = (aW - gap*(nCols-1) - lpad - rpad)/float(nCols)
        aH0 = aH
        aH -= tpad + bpad
        W,H0,_C0,C2 = self._findSplit(canv,cw,nCols*aH,paraFix=False)
        if not _C0:
            raise ValueError(
                    "%s cannot make initial split aW=%r aH=%r ie cw=%r ah=%r\ncontent=%s" % (
                        self.identity(),aW,aH,cw,nCols*aH,
                        [f.__class__.__name__ for f in self._content],
                        ))
        _fres = {}
        def splitFunc(ah,endSlack=0):
            if ah not in _fres:
                c = []
                w = 0
                h = 0
                cn = None
                icheck = nCols-2 if endSlack else -1
                for i in range(nCols):
                    wi, hi, c0, c1 = self._findSplit(canv,cw,ah,content=cn,paraFix=False)
                    w = max(w,wi)
                    h = max(h,hi)
                    c.append(c0)
                    if i==icheck:
                        wc, hc, cc0, cc1 = self._findSplit(canv,cw,2*ah,content=c1,paraFix=False)
                        if hc<=(1+endSlack)*ah:
                            c.append(c1)
                            h = ah-1e-6
                            cn = []
                            break
                    cn = c1
                _fres[ah] = ah+100000*int(cn!=[]),cn==[],(w,h,c,cn)
            return _fres[ah][2]

        endSlack = 0
        if C2:
            H = aH
        else:
            #we are short so use H0 to figure out what to use
            import math

            def func(ah):
                splitFunc(ah)
                return _fres[ah][0]

            def gss(f, a, b, tol=1, gr=(math.sqrt(5) + 1) / 2):
                c = b - (b - a) / gr
                d = a + (b - a) / gr
                while abs(a - b) > tol:
                    if f(c) < f(d):
                        b = d
                    else:
                        a = c

                    # we recompute both c and d here to avoid loss of precision which may lead to incorrect results or infinite loop
                    c = b - (b - a) / gr
                    d = a + (b - a) / gr

                F = [(x,tf,v) for x,tf,v in _fres.values() if tf]
                if F:
                    F.sort()
                    return F[0][2]
                return None

            H = min(int(H0/float(nCols)+self.spaceAfter*0.4),aH)
            splitFunc(H)
            if not _fres[H][1]:
                H = gss(func,H,aH)
                if H:
                    W, H0, _C0, C2 = H
                    H = H0
                    endSlack = False
                else:
                    H = aH
                    endSlack = self.endSlack
            else:
                H1 = H0/float(nCols)
                splitFunc(H1)
                if not _fres[H1][1]:
                    H = gss(func,H,aH)
                    if H:
                        W, H0, _C0, C2 = H
                        H = H0
                        endSlack = False
                    else:
                        H = aH
                        endSlack = self.endSlack
            assert not C2, "unexpected non-empty C2"
        W1, H1, C, C1 = splitFunc(H, endSlack)
        _fres.clear()
        no_split = False
        if C[0]==[] and C[1]==[] and C1:
            # Fix - for errror ->
            #   ...
            #   File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/platypus/flowables.py", line 1785, in wrap
            #     H1, G = self._generated_content(aW,aH)
            #   File "/home/ox23/Python.projects/cv/workroom/reportlab/charts_in_balanced_column_with_legend.py", line 266, in _generated_content
            #     Ci = C[i]
            # IndexError: list index out of range
            no_split = True
            #Old source
            #no split situation
            # C, C1 = [C1,C[1]], C[0]

        x1 = frame._x1
        y1 = frame._y1
        fw = frame._width
        ftop = y1+bpad+tpad+aH
        fh = H1 + bpad + tpad

        # Fix - for errror ->
        #   ...
        #   File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/platypus/flowables.py", line 1785, in wrap
        #     H1, G = self._generated_content(aW,aH)
        #   File "/home/ox23/Python.projects/cv/workroom/reportlab/charts_in_balanced_column_with_legend.py", line 266, in _generated_content
        #     Ci = C[i]
        # IndexError: list index out of range
        # related for line 151
        if no_split:
            return fh, [PageBreak(), self._create_next(C1)]

        y2 = ftop - fh
        dx = aW / float(nCols)
        if leftExtraIndent or rightExtraIndent:
            indenter0 = Indenter(-leftExtraIndent,-rightExtraIndent)
            indenter1 = Indenter(leftExtraIndent,rightExtraIndent)
        else:
            indenter0 = indenter1 = None

        showBoundary=self.showBoundary if self.showBoundary is not None else frame.showBoundary
        obx = x1+leftExtraIndent+frame._leftPadding
        F = [Frame(obx+i*dx,y2,dx,fh,
                leftPadding=lpad if not i else hgap, bottomPadding=bpad,
                rightPadding=rpad if i==nCols-1 else hgap, topPadding=tpad,
                id='%s-%d' %(self.name,i),
                showBoundary=showBoundary,
                overlapAttachedSpace=frame._oASpace,
                _debug=frame._debug) for i in range(nCols)]

        #we are going to modify the current template
        T=self._doctemplateAttr('pageTemplate')
        if T is None:
            raise LayoutError('%s used in non-doctemplate environment' % self.identity())

        BGs = getattr(frame,'_frameBGs',None)
        xbg = bg = BGs[-1] if BGs else None

        class TAction(ActionFlowable):
            '''a special Action flowable that sets stuff on the doc template T'''
            def __init__(self, bgs=[],F=[],f=None):
                Flowable.__init__(self)
                self.bgs = bgs
                self.F = F
                self.f = f

            def apply(self,doc,T=T):
                T.frames = self.F
                frame._frameBGs = self.bgs
                doc.handle_currentFrame(self.f.id)
                frame._frameBGs = self.bgs

        if bg:
            #G.append(Spacer(1e-5,1e-5))
            #G[-1].__id__ = 'spacer0'
            xbg = _ExtendBG(y2,fh,bg,frame)
            G.append(xbg)

        oldFrames = T.frames
        G.append(TAction([],F,F[0]))
        if indenter0: G.append(indenter0)
        doBox = (self._boxStrokeColor and self._boxStrokeWidth and self._boxStrokeWidth>=0) or self._boxFillColor
        doVLines = self._vLinesStrokeColor and self._vLinesStrokeWidth and self._vLinesStrokeWidth>=0
        if doBox or doVLines:
            obm = self._boxMargin
            if not obm: obm = (0,0,0,0)
            if len(obm)==1:
                obmt = obml = obmr = obmb = obm[0]
            elif len(obm)==2:
                obmt = obmb = obm[0]
                obml = obmr = obm[1]
            elif len(obm)==3:
                obmt = obm[0]
                obml = obmr = obm[1]
                obmb = obm[2]
            elif len(obm)==4:
                obmt = obm[0]
                obmr = obm[1]
                obmb = obm[2]
                obml = obm[3]
            else:
                raise ValueError('Invalid value %s for boxMargin' % repr(obm))
            obx1 = obx - obml
            obx2 = F[-1]._x1+F[-1]._width + obmr
            oby2 = y2-obmb
            obh = fh+obmt+obmb
            oby1 = oby2+obh
            if doBox:
                box = _AbsRect(obx1,oby2, obx2-obx1, obh,
                        fillColor=self._boxFillColor,
                        strokeColor=self._boxStrokeColor,
                        strokeWidth=self._boxStrokeWidth,
                        )
            if doVLines:
                vLines = []
                for i in range(1,nCols):
                    vlx = 0.5*(F[i]._x1 + F[i-1]._x1+F[i-1]._width)
                    vLines.append(_AbsLine(vlx,oby2,vlx,oby1,strokeWidth=self._vLinesStrokeWidth,strokeColor=self._vLinesStrokeColor))
        else:
            oby1 = ftop
            oby2 = y2

        if doBox: G.append(box)
        if doVLines: G.extend(vLines)
        sa = self.getSpaceAfter()
        for i in range(nCols):
            Ci = C[i]

            if Ci:
                Ci = KeepInFrame(W1,H1,Ci,mode='shrink')
                sa = max(sa,Ci.getSpaceAfter())
                G.append(Ci)

            if i!=nCols-1:
                G.append(FrameBreak)

        G.append(TAction(BGs,oldFrames,frame))
        if xbg:
            if C1: sa = 0
            xbg._y = min(y2,oby2) - sa
            xbg._height = max(ftop,oby1) - xbg._y
        if indenter1: G.append(indenter1)
        if C1:
            G.append(self._create_next(C1))
        return fh, G


class Drawing(Drawing):
    """
        Fix for issue
        When it uses inside BalancedColumns

        Fatal Python error: _Py_CheckRecursiveCall: Cannot recover from stack overflow.
        Python runtime state: initialized

        Current thread 0x00007ff4692c6740 (most recent call first):
          File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 219 in __getattr__
          ...
          File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 231 in parent
          File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 221 in __getattr__
          File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 231 in parent
          ...

        Process finished with exit code 134 (interrupted by signal 6: SIGABRT)

        flowables._FindSplitterMixin:
        line #1266: S = cdeepcopy(f).splitOn(canv,availWidth,aH)

        variants of resolving

        return self._copy(self.__class__())

        or

        c = copy(self)  #shallow
        self._reset()
        c.copyContent() #partially deep?
        return c

        my preference
        (It has no sense to split on deep-copied flowable. Flowable that has been split always returns new instances)

        return self
    """

    def deepcopy(self):
        # Fix for issue
        # When it uses inside BalancedColumns
        #
        # Fatal Python error: _Py_CheckRecursiveCall: Cannot recover from stack overflow.
        # Python runtime state: initialized
        #
        # Current thread 0x00007ff4692c6740 (most recent call first):
        #   File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 219 in __getattr__
        #   ...
        #   File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 231 in parent
        #   File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 221 in __getattr__
        #   File "/home/ox23/Python.projects/cv/.venv/lib/python3.9/site-packages/reportlab/graphics/widgetbase.py", line 231 in parent
        #   ...
        #
        # Process finished with exit code 134 (interrupted by signal 6: SIGABRT)
        #
        # flowables._FindSplitterMixin:
        # line #1266: S = cdeepcopy(f).splitOn(canv,availWidth,aH)

        # variants of resolving

        # return self._copy(self.__class__())

        # c = copy(self)  #shallow
        # self._reset()
        # c.copyContent() #partially deep?
        # return c

        return self
