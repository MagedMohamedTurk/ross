import pickle

import bokeh.palettes as bp
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from bokeh.layouts import gridplot
from bokeh.models import ColumnDataSource, ColorBar, Arrow, NormalHead, Label
from bokeh.plotting import figure, output_file, show
from bokeh.transform import linear_cmap
from scipy import interpolate

# set bokeh palette of colors
bokeh_colors = bp.RdGy[11]


class Results(np.ndarray):
    """Class used to store results and provide plots.
    This class subclasses np.ndarray to provide additional info and a plot
    method to the calculated results from Rotor.
    Metadata about the results should be stored on info as a dictionary to be
    used on plot configurations and so on.
    Additional attributes can be passed as a dictionary in new_attributes kwarg.
    """

    def __new__(cls, input_array, new_attributes=None):
        obj = np.asarray(input_array).view(cls)

        for k, v in new_attributes.items():
            setattr(obj, k, v)

        # save new attributes names to create them on array finalize
        obj._new_attributes = new_attributes

        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return

        try:
            for k, v in obj._new_attributes.items():
                setattr(self, k, getattr(obj, k, v))
        except AttributeError:
            return

    def __reduce__(self):

        pickled_state = super().__reduce__()
        new_state = pickled_state[2] + (self._new_attributes,)

        return pickled_state[0], pickled_state[1], new_state

    def __setstate__(self, state):
        self._new_attributes = state[-1]
        for k, v in self._new_attributes.items():
            setattr(self, k, v)
        super().__setstate__(state[0:-1])

    def save(self, file):
        with open(file, mode="wb") as f:
            pickle.dump(self, f)

    def plot(self, *args, **kwargs):
        raise NotImplementedError


class CampbellResults(Results):
    def plot(self, harmonics=[1], wn=False, output_html=False, fig=None, ax=None, **kwargs):
        """Plot campbell results.
        Parameters
        ----------
        harmonics: list, optional
            List withe the harmonics to be plotted.
            The default is to plot 1x.
        fig : matplotlib figure, optional
            Figure to insert axes with log_dec colorbar.
        ax : matplotlib axes, optional
            Axes in which the plot will be drawn.
        output_html : Boolean, optional
            outputs a html file.
            Default is False
        Returns
        -------
        ax : matplotlib axes
            Returns the axes object with the plot.
        """

        # results for campbell is an array with [speed_range, wd/log_dec/whirl]

        if fig is None and ax is None:
            fig, ax = plt.subplots()

        wd = self[..., 0]
        if wn is True:
            wn = self[..., 4]
        log_dec = self[..., 1]
        whirl = self[..., 2]
        speed_range = self[..., 3]

        log_dec_map = log_dec.flatten()

        default_values = dict(
            cmap="viridis",
            vmin=min(log_dec_map),
            vmax=max(log_dec_map),
            s=30,
            alpha=1.0,
        )

        for k, v in default_values.items():
            kwargs.setdefault(k, v)

        # bokeh plot - output to static HTML file
        if output_html:
            output_file("Campbell_diagram.html")

        # bokeh plot - create a new plot
        camp = figure(
            tools="pan, box_zoom, wheel_zoom, reset, save",
            sizing_mode="stretch_both",
            title="Campbell Diagram - Damped Natural Frequency Map",
            x_axis_label="Rotor speed (rad/s)",
            y_axis_label="Damped natural frequencies (rad/s)",
        )

        for mark, whirl_dir, legend in zip(
            ["^", "o", "v"], [0.0, 0.5, 1.0], ["Foward", "Mixed", "Backward"]
        ):
            num_frequencies = wd.shape[1]
            for i in range(num_frequencies):
                if wn is True:
                    w_i = wn[:, i]
                else:
                    w_i = wd[:, i]
                whirl_i = whirl[:, i]
                log_dec_i = log_dec[:, i]
                speed_range_i = speed_range[:, i]

                whirl_mask = whirl_i == whirl_dir
                if whirl_mask.shape[0] == 0:
                    continue
                else:
                    im = ax.scatter(
                        speed_range_i[whirl_mask],
                        w_i[whirl_mask],
                        c=log_dec_i[whirl_mask],
                        marker=mark,
                        **kwargs,
                    )

                    # Bokeh plot
                    source = ColumnDataSource(
                        dict(
                            x=speed_range_i[whirl_mask],
                            y=w_i[whirl_mask],
                            color=log_dec_i[whirl_mask],
                        )
                    )
                    color_mapper = linear_cmap(
                        field_name="color",
                        palette=bp.viridis(256),
                        low=min(log_dec_map),
                        high=max(log_dec_map),
                    )
                    camp.scatter(
                        x="x",
                        y="y",
                        color=color_mapper,
                        marker=mark,
                        fill_alpha=1.0,
                        size=9,
                        muted_color=color_mapper,
                        muted_alpha=0.2,
                        source=source,
                        legend=legend,
                    )

        ax.plot(
            speed_range[:, 0],
            speed_range[:, 0],
            color="k",
            linewidth=1.5,
            linestyle="-.",
            alpha=0.75,
            label="Rotor speed",
        )

        camp.line(
            x=speed_range[:, 0],
            y=speed_range[:, 0],
            line_width=3,
            color=bokeh_colors[0],
            line_dash="dotdash",
            line_alpha=0.75,
            legend="Rotor speed",
            muted_color=bokeh_colors[0],
            muted_alpha=0.2,
        )

        color_bar = ColorBar(
            color_mapper=color_mapper["transform"],
            width=8,
            location=(0, 0),
            title="log dec",
            title_text_font_style="bold italic",
            title_text_align="center",
        )

        camp.legend.background_fill_alpha = 0.1
        camp.legend.click_policy = "mute"
        camp.legend.location = "top_left"
        camp.add_layout(color_bar, "right")
        show(camp)

        if len(fig.axes) == 1:
            cbar = fig.colorbar(im)
            cbar.ax.set_ylabel("log dec")
            cbar.solids.set_edgecolor("face")

            forward_label = mpl.lines.Line2D(
                [], [], marker="^", lw=0, color="tab:blue", alpha=1.0, label="Forward"
            )
            backward_label = mpl.lines.Line2D(
                [], [], marker="v", lw=0, color="tab:blue", alpha=1.0, label="Backward"
            )
            mixed_label = mpl.lines.Line2D(
                [], [], marker="o", lw=0, color="tab:blue", alpha=1.0, label="Mixed"
            )

            legend = plt.legend(
                handles=[forward_label, backward_label, mixed_label], loc=2
            )

            ax.add_artist(legend)

            ax.set_xlabel("Rotor speed ($rad/s$)")
            ax.set_ylabel("Damped natural frequencies ($rad/s$)")
            ax.set_title("Campbell Diagram - Damped Natural Frequency Map")

        return fig, ax


class FrequencyResponseResults(Results):
    def plot_magnitude(self, inp, out, ax=None, units="m", **kwargs):
        """Plot frequency response.
        This method plots the frequency response magnitude given an output and
        an input.
        Parameters
        ----------
        inp : int
            Input.
        out : int
            Output.
        ax : matplotlib.axes, optional
            Matplotlib axes where the phase will be plotted.
            If None creates a new.
        kwargs : optional
            Additional key word arguments can be passed to change
            the plot (e.g. linestyle='--')
        Returns
        -------
        ax : matplotlib.axes
            Matplotlib axes with amplitude plot.
        mag_plot : bokeh plot axes
            Bokeh plot axes with amplitude plot.
        Examples
        --------
        """
        if ax is None:
            ax = plt.gca()

        frequency_range = self.frequency_range
        mag = self.magnitude

        ax.plot(frequency_range, mag[inp, out, :], **kwargs)

        ax.set_xlim(0, max(frequency_range))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="lower"))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="upper"))

        if units == "m":
            ax.set_ylabel("Amplitude $(m)$")
            y_axis_label = "Amplitude (m)"
        elif units == "mic-pk-pk":
            ax.set_ylabel("Amplitude $(\mu pk-pk)$")
            y_axis_label = "Amplitude (\mu pk-pk)"
        else:
            ax.set_ylabel("Amplitude $(dB)$")
            y_axis_label = "Amplitude (dB"

        ax.set_xlabel("Frequency (rad/s)")

        # bokeh plot - create a new plot
        mag_plot = figure(
            tools="pan, box_zoom, wheel_zoom, reset, save",
            width=900,
            height=400,
            title="Frequency Response - Magnitude",
            x_axis_label="Frequency",
            y_axis_label=y_axis_label,
        )
        source = ColumnDataSource(dict(x=frequency_range, y=mag[inp, out, :]))
        mag_plot.line(
            x="x",
            y="y",
            source=source,
            line_color=bokeh_colors[0],
            line_alpha=1.0,
            line_width=3,
        )

        return ax, mag_plot

    def plot_phase(self, inp, out, ax=None, **kwargs):
        """Plot frequency response.
        This method plots the frequency response phase given an output and
        an input.
        Parameters
        ----------
        inp : int
            Input.
        out : int
            Output.
        ax : matplotlib.axes, optional
            Matplotlib axes where the phase will be plotted.
            If None creates a new.
        kwargs : optional
            Additional key word arguments can be passed to change
            the plot (e.g. linestyle='--')
        Returns
        -------
        ax : matplotlib.axes
            Matplotlib axes with phase plot.
        phase_plot : bokeh plot axes
            Bokeh plot axes with phase plot.
        Examples
        --------
        """
        if ax is None:
            ax = plt.gca()

        frequency_range = self.frequency_range
        phase = self.phase

        ax.plot(frequency_range, phase[inp, out, :], **kwargs)

        ax.set_xlim(0, max(frequency_range))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="lower"))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="upper"))

        ax.set_ylabel("Phase")
        ax.set_xlabel("Frequency (rad/s)")

        # bokeh plot - create a new plot
        phase_plot = figure(
            tools="pan, box_zoom, wheel_zoom, reset, save",
            width=900,
            height=400,
            title="Frequency Response - Phase",
            x_axis_label="Frequency",
            y_axis_label="Phase",
        )
        source = ColumnDataSource(dict(x=frequency_range, y=phase[inp, out, :]))
        phase_plot.line(
            x="x",
            y="y",
            source=source,
            line_color=bokeh_colors[0],
            line_alpha=1.0,
            line_width=3,
        )

        return ax, phase_plot

    def plot(self, inp, out, output_html=False, ax0=None, ax1=None, **kwargs):
        """Plot frequency response.
        This method plots the frequency response given
        an output and an input.
        Parameters
        ----------
        inp : int
            Input.
        out : int
            Output.
        output_html : Boolean, optional
            outputs a html file.
            Default is False
        ax0 : matplotlib.axes, bokeh plot axes optional
            Matplotlib and bokeh plot axes where the amplitude will be plotted.
            If None creates a new.
        ax1 : matplotlib.axes, bokeh plot axes optional
            Matplotlib and bokeh plot axes where the phase will be plotted.
            If None creates a new.
        kwargs : optional
            Additional key word arguments can be passed to change
            the plot (e.g. linestyle='--')
        Returns
        -------
        ax0 : matplotlib.axes
            Matplotlib axes with amplitude plot.
        ax1 : matplotlib.axes
            Matplotlib axes with phase plot.
        bk_ax0 : bokeh plot axes
            Bokeh plot axes with amplitude plot
        bk_ax1 : bokeh plot axes
            Bokeh plot axes with phase plot
        Examples
        --------
        """
        if ax0 is None and ax1 is None:
            fig, (ax0, ax1) = plt.subplots(2)

        # bokeh plot - output to static HTML file
        if output_html:
            output_file("freq_response.html")

        # matplotlib axes
        ax0 = self.plot_magnitude(inp, out, ax=ax0)[0]
        ax1 = self.plot_phase(inp, out, ax=ax1)[0]

        # bokeh plot axes
        bk_ax0 = self.plot_magnitude(inp, out, ax=ax0)[1]
        bk_ax1 = self.plot_phase(inp, out, ax=ax1)[1]

        ax0.set_xlabel("")

        # show the bokeh plot results
        grid_plots = gridplot([[bk_ax0], [bk_ax1]])
        show(grid_plots)

        return ax0, ax1, bk_ax0, bk_ax1

    def plot_freq_response_grid(self, outs, inps, ax=None, **kwargs):
        """Plot frequency response.
        This method plots the frequency response given
        an output and an input.
        Parameters
        ----------
        outs : list
            List with the desired outputs.
        inps : list
            List with the desired outputs.
        ax : array with matplotlib.axes, optional
            Matplotlib axes array created with plt.subplots.
            It needs to have a shape of (2*inputs, outputs).
        Returns
        -------
        ax : array with matplotlib.axes, optional
            Matplotlib axes array created with plt.subplots.
        """
        if ax is None:
            fig, ax = plt.subplots(
                len(inps) * 2,
                len(outs),
                sharex=True,
                figsize=(4 * len(outs), 3 * len(inps)),
            )
            fig.subplots_adjust(hspace=0.001, wspace=0.25)

        if len(outs) > 1:
            for i, out in enumerate(outs):
                for j, inp in enumerate(inps):
                    self.plot_magnitude(out, inp, ax=ax[2 * i, j], **kwargs)
                    self.plot_phase(out, inp, ax=ax[2 * i + 1, j], **kwargs)
        else:
            for i, inp in enumerate(inps):
                self.plot_magnitude(outs[0], inp, ax=ax[2 * i], **kwargs)
                self.plot_phase(outs[0], inp, ax=ax[2 * i + 1], **kwargs)

        return ax


class ForcedResponseResults(Results):
    def plot_magnitude(self, dof, ax=None, units="m", **kwargs):
        """Plot frequency response.
        This method plots the frequency response magnitude given an output and
        an input.
        Parameters
        ----------
        dof : int
            Degree of freedom.
        ax : matplotlib.axes, optional
            Matplotlib axes where the phase will be plotted.
            If None creates a new.
        units : str
            Units to plot the magnitude ('m' or 'mic-pk-pk')
        kwargs : optional
            Additional key word arguments can be passed to change
            the plot (e.g. linestyle='--')
        Returns
        -------
        ax : matplotlib.axes
            Matplotlib axes with phase plot.
        mag_plot : bokeh axes
            bokeh axes with magnitude plot
        Examples
        --------
        """
        if ax is None:
            ax = plt.gca()

        frequency_range = self.frequency_range
        mag = self.magnitude

        if units == "m":
            ax.set_ylabel("Amplitude $(m)$")
            y_axis_label = "Amplitude (m)"
        elif units == "mic-pk-pk":
            mag = 2 * mag * 1e6
            ax.set_ylabel("Amplitude $(\mu pk-pk)$")
            y_axis_label = "Amplitude $(\mu pk-pk)$"

        # matplotlib plotting
        ax.plot(frequency_range, mag[dof], **kwargs)

        ax.set_xlim(0, max(frequency_range))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="lower"))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="upper"))

        ax.set_xlabel("Frequency (rad/s)")
        ax.legend()

        # bokeh plot - create a new plot
        mag_plot = figure(
            tools="pan, box_zoom, wheel_zoom, reset, save",
            width=900,
            height=400,
            title="Forced Response - Magnitude",
            x_axis_label="Frequency",
            x_range=[0, max(frequency_range)],
            y_axis_label=y_axis_label,
        )
        source = ColumnDataSource(dict(x=frequency_range, y=mag[dof]))
        mag_plot.line(
            x="x",
            y="y",
            source=source,
            line_color=bokeh_colors[0],
            line_alpha=1.0,
            line_width=3,
        )

        return ax, mag_plot

    def plot_phase(self, dof, ax=None, **kwargs):
        """Plot frequency response.
        This method plots the frequency response phase given an output and
        an input.
        Parameters
        ----------
        dof : int
            Degree of freedom.
        ax : matplotlib.axes, optional
            Matplotlib axes where the phase will be plotted.
            If None creates a new.
        kwargs : optional
            Additional key word arguments can be passed to change
            the plot (e.g. linestyle='--')
        Returns
        -------
        ax : matplotlib.axes
            Matplotlib axes with phase plot.
        phase_plot : bokeh axes
            Bokeh axes with phase plot
        Examples
        --------
        """
        if ax is None:
            ax = plt.gca()

        frequency_range = self.frequency_range
        phase = self.phase

        ax.plot(frequency_range, phase[dof], **kwargs)

        ax.set_xlim(0, max(frequency_range))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="lower"))
        ax.yaxis.set_major_locator(mpl.ticker.MaxNLocator(prune="upper"))

        ax.set_ylabel("Phase")
        ax.set_xlabel("Frequency (rad/s)")
        ax.legend()

        # bokeh plot - create a new plot
        phase_plot = figure(
            tools="pan, box_zoom, wheel_zoom, reset, save",
            width=900,
            height=400,
            title="Forced Response - Magnitude",
            x_axis_label="Frequency",
            x_range=[0, max(frequency_range)],
            y_axis_label="Phase",
        )
        source = ColumnDataSource(dict(x=frequency_range, y=phase[dof]))
        phase_plot.line(
            x="x",
            y="y",
            source=source,
            line_color=bokeh_colors[0],
            line_alpha=1.0,
            line_width=3,
        )

        return ax, phase_plot

    def plot(self, dof, output_html=False, ax0=None, ax1=None, **kwargs):
        """Plot frequency response.
        This method plots the frequency response given
        an output and an input.
        Parameters
        ----------
        dof : int
            Degree of freedom.
        output_html : Boolean, optional
            outputs a html file.
            Default is False
        ax0 : matplotlib.axes, optional
            Matplotlib axes where the amplitude will be plotted.
            If None creates a new.
        ax1 : matplotlib.axes, optional
            Matplotlib axes where the phase will be plotted.
            If None creates a new.
        kwargs : optional
            Additional key word arguments can be passed to change
            the plot (e.g. linestyle='--')
        Returns
        -------
        ax0 : matplotlib.axes
            Matplotlib axes with amplitude plot.
        ax1 : matplotlib.axes
            Matplotlib axes with phase plot.
        bk_ax0 : bokeh axes
            Bokeh axes with amplitude plot.
        bk_ax1 : bokeh axes
            Bokeh axes with phase plot.
        Examples
        --------
        """
        if ax0 is None and ax1 is None:
            fig, (ax0, ax1) = plt.subplots(2)

        ax0 = self.plot_magnitude(dof, ax=ax0, **kwargs)[0]
        # remove label from phase plot
        kwargs.pop("label", None)
        kwargs.pop("units", None)
        ax1 = self.plot_phase(dof, ax=ax1, **kwargs)[0]

        ax0.set_xlabel("")
        ax0.legend()

        # bokeh plot - output to static HTML file
        if output_html:
            output_file("forced_rsponse.html")

        # bokeh plot axes
        bk_ax0 = self.plot_magnitude(dof, ax=ax0, **kwargs)[1]
        bk_ax1 = self.plot_phase(dof, ax=ax1, **kwargs)[1]

        # show the bokeh plot results
        grid_plots = gridplot([[bk_ax0], [bk_ax1]])
        show(grid_plots)

        return ax0, ax1, bk_ax0, bk_ax1


class ModeShapeResults(Results):
    def plot(self, mode=None, evec=None, fig=None, ax=None):
        if ax is None:
            fig = plt.figure()
            ax = fig.gca(projection="3d")

        evec0 = self[:, mode]
        nodes = self.nodes
        nodes_pos = self.nodes_pos
        kappa_modes = self.kappa_modes
        elements_length = self.elements_length

        modex = evec0[0::4]
        modey = evec0[1::4]
        xmax, ixmax = max(abs(modex)), np.argmax(abs(modex))
        ymax, iymax = max(abs(modey)), np.argmax(abs(modey))

        if ymax > 0.4 * xmax:
            evec0 /= modey[iymax]
        else:
            evec0 /= modex[ixmax]

        modex = evec0[0::4]
        modey = evec0[1::4]

        num_points = 201
        c = np.linspace(0, 2 * np.pi, num_points)
        circle = np.exp(1j * c)

        x_circles = np.zeros((num_points, len(nodes)))
        y_circles = np.zeros((num_points, len(nodes)))
        z_circles_pos = np.zeros((num_points, len(nodes)))

        kappa_mode = kappa_modes[mode]

        for node in nodes:
            x = modex[node] * circle
            x_circles[:, node] = np.real(x)
            y = modey[node] * circle
            y_circles[:, node] = np.real(y)
            z_circles_pos[:, node] = nodes_pos[node]

        # plot lines
        nn = 21
        zeta = np.linspace(0, 1, nn)
        onn = np.ones_like(zeta)

        zeta = zeta.reshape(nn, 1)
        onn = onn.reshape(nn, 1)

        xn = np.zeros(nn * (len(nodes) - 1))
        yn = np.zeros(nn * (len(nodes) - 1))
        zn = np.zeros(nn * (len(nodes) - 1))

        N1 = onn - 3 * zeta ** 2 + 2 * zeta ** 3
        N2 = zeta - 2 * zeta ** 2 + zeta ** 3
        N3 = 3 * zeta ** 2 - 2 * zeta ** 3
        N4 = -zeta ** 2 + zeta ** 3

        for Le, n in zip(elements_length, nodes):
            node_pos = nodes_pos[n]
            Nx = np.hstack((N1, Le * N2, N3, Le * N4))
            Ny = np.hstack((N1, -Le * N2, N3, -Le * N4))

            xx = [4 * n, 4 * n + 3, 4 * n + 4, 4 * n + 7]
            yy = [4 * n + 1, 4 * n + 2, 4 * n + 5, 4 * n + 6]

            pos0 = nn * n
            pos1 = nn * (n + 1)
            xn[pos0:pos1] = Nx @ evec0[xx].real
            yn[pos0:pos1] = Ny @ evec0[yy].real
            zn[pos0:pos1] = (node_pos * onn + Le * zeta).reshape(nn)

        for node in nodes:
            ax.plot(
                x_circles[10:, node],
                y_circles[10:, node],
                z_circles_pos[10:, node],
                color=kappa_mode[node],
                linewidth=0.5,
                zdir="x",
            )
            ax.scatter(
                x_circles[10, node],
                y_circles[10, node],
                z_circles_pos[10, node],
                s=5,
                color=kappa_mode[node],
                zdir="x",
            )

        ax.plot(xn, yn, zn, "k--", zdir="x")

        # plot center line
        zn_cl0 = -(zn[-1] * 0.1)
        zn_cl1 = zn[-1] * 1.1
        zn_cl = np.linspace(zn_cl0, zn_cl1, 30)
        ax.plot(zn_cl * 0, zn_cl * 0, zn_cl, "k-.", linewidth=0.8, zdir="x")

        ax.set_zlim(-2, 2)
        ax.set_ylim(-2, 2)
        ax.set_xlim(zn_cl0 - 0.1, zn_cl1 + 0.1)

        ax.set_title(
            f"$speed$ = {self.w:.1f} rad/s\n$"
            f"\frequency_range_d$ = {self.wd[mode]:.1f} rad/s\n"
            f"$log dec$ = {self.log_dec[mode]:.1f}"
        )

        return fig, ax

class StaticResults(Results):
    def plot(self, output_html=False):
        """Plot static analysis graphs.
        This method plots:
            free-body diagram,
            deformed shaft,
            shearing force diagram,
            bending moment diagram.

        Parameters
        ----------
        output_html : Boolean, optional
            outputs a html file.
            Default is False

        Returns
        -------
        grid_plots : bokeh.gridplot
        --------
        """

        # bokeh plot - output to static HTML file
        if output_html:
            output_file("static_analysis.html")
        
        disp_y = np.array(self[0])
        Vx = np.array(self[1])
        Bm = np.array(self[2])

        df_shaft = self.df_shaft
        df_disks = self.df_disks
        df_bearings = self.df_bearings
        nodes = self.nodes
        nodes_pos = self.nodes_pos
        Vx_axis = self.Vx_axis

        source = ColumnDataSource(
            data=dict(x0=nodes_pos, y0=disp_y * 1000, y1=[0] * len(nodes_pos))
        )

        TOOLS = "pan,wheel_zoom,box_zoom,reset,save,box_select,hover"
        TOOLTIPS = [
            ("Shaft lenght:", "@x0"),
            ("Underformed:", "@y1"),
            ("Displacement:", "@y0"),
        ]

        # create displacement plot
        disp_graph = figure(
            tools=TOOLS,
            tooltips=TOOLTIPS,
            width=800,
            height=400,
            title="Static Analysis",
            x_axis_label="shaft lenght",
            y_axis_label="lateral displacement",
        )

        interpolated = interpolate.interp1d(
            source.data["x0"], source.data["y0"], kind="cubic"
        )
        xnew = np.linspace(
            source.data["x0"][0],
            source.data["x0"][-1],
            num=len(nodes_pos) * 20,
            endpoint=True,
        )

        ynew = interpolated(xnew)
        auxsource = ColumnDataSource(data=dict(x0=xnew, y0=ynew, y1=[0] * len(xnew)))

        disp_graph.line(
            "x0",
            "y0",
            source=auxsource,
            legend="Deformed shaft",
            line_width=3,
            line_color=bokeh_colors[9],
        )
        disp_graph.circle(
            "x0",
            "y0",
            source=source,
            legend="Deformed shaft",
            size=8,
            fill_color=bokeh_colors[9],
        )
        disp_graph.line(
            "x0",
            "y1",
            source=source,
            legend="underformed shaft",
            line_width=3,
            line_color=bokeh_colors[0],
        )
        disp_graph.circle(
            "x0",
            "y1",
            source=source,
            legend="underformed shaft",
            size=8,
            fill_color=bokeh_colors[0],
        )

        # create a new plot for free body diagram (FDB)
        y_range = []
        sh_weight = sum(df_shaft["m"].values) * 9.8065
        y_range.append(sh_weight)
        for i, node in enumerate(df_bearings["n"]):
            y_range.append(
                -disp_y[node] * df_bearings.loc[i, "kyy"].coefficient[0]
            )

        shaft_end = nodes_pos[-1]
        FBD = figure(
            tools=TOOLS,
            width=800,
            height=400,
            title="Free-Body Diagram",
            x_axis_label="shaft lenght",
            y_axis_label="Force",
            x_range=[-0.1 * shaft_end, 1.1 * shaft_end],
            y_range=[-max(y_range) * 1.4, max(y_range) * 1.4],
        )

        FBD.line("x0", "y1", source=source, line_width=5, line_color=bokeh_colors[0])

        # FBD - plot arrows indicating shaft weight distribution
        text = str("%.1f" % sh_weight)
        FBD.line(
            x=nodes_pos,
            y=[sh_weight] * len(nodes_pos),
            line_width=2,
            line_color=bokeh_colors[0],
        )

        for node in nodes_pos:
            FBD.add_layout(
                Arrow(
                    end=NormalHead(
                        fill_color=bokeh_colors[7],
                        fill_alpha=1.0,
                        size=16,
                        line_width=2,
                        line_color=bokeh_colors[0],
                    ),
                    x_start=node,
                    y_start=sh_weight,
                    x_end=node,
                    y_end=0,
                )
            )

        FBD.add_layout(
            Label(
                x=nodes_pos[0],
                y=sh_weight,
                text="W = " + text + "N",
                text_font_style="bold",
                text_baseline="top",
                text_align="left",
                y_offset=20,
            )
        )

        # FBD - calculate the reaction force of bearings and plot arrows
        for i, node in enumerate(df_bearings["n"]):
            Fb = -disp_y[node] * df_bearings.loc[i, "kyy"].coefficient[0]
            text = str("%.1f" % Fb)
            FBD.add_layout(
                Arrow(
                    end=NormalHead(
                        fill_color=bokeh_colors[7],
                        fill_alpha=1.0,
                        size=16,
                        line_width=2,
                        line_color=bokeh_colors[0],
                    ),
                    x_start=nodes_pos[node],
                    y_start=-Fb,
                    x_end=nodes_pos[node],
                    y_end=0,
                )
            )
            FBD.add_layout(
                Label(
                    x=nodes_pos[node],
                    y=-Fb,
                    text="Fb = " + text + "N",
                    text_font_style="bold",
                    text_baseline="bottom",
                    text_align="center",
                    y_offset=-20,
                )
            )

        # FBD - plot arrows indicating disk weight
        if len(df_disks) != 0:
            for i, node in enumerate(df_disks["n"]):
                Fd = df_disks.loc[i, "m"] * 9.8065
                text = str("%.1f" % Fd)
                FBD.add_layout(
                    Arrow(
                        end=NormalHead(
                            fill_color=bokeh_colors[7],
                            fill_alpha=1.0,
                            size=16,
                            line_width=2,
                            line_color=bokeh_colors[0],
                        ),
                        x_start=nodes_pos[node],
                        y_start=Fd,
                        x_end=nodes_pos[node],
                        y_end=0,
                    )
                )
                FBD.add_layout(
                    Label(
                        x=nodes_pos[node],
                        y=Fd,
                        text="Fd = " + text + "N",
                        text_font_style="bold",
                        text_baseline="top",
                        text_align="center",
                        y_offset=20,
                    )
                )

        # Shearing Force Diagram plot (SF)
        source_SF = ColumnDataSource(data=dict(x=Vx_axis, y=Vx))
        TOOLTIPS_SF = [("Shearing Force:", "@y")]
        SF = figure(
            tools=TOOLS,
            tooltips=TOOLTIPS_SF,
            width=800,
            height=400,
            title="Shearing Force Diagram",
            x_axis_label="Shaft lenght",
            y_axis_label="Force",
            x_range=[-0.1 * shaft_end, 1.1 * shaft_end],
        )
        SF.line("x", "y", source=source_SF, line_width=4, line_color=bokeh_colors[0])
        SF.circle("x", "y", source=source_SF, size=8, fill_color=bokeh_colors[0])

        # SF - plot centerline
        SF.line(
            [-0.1 * shaft_end, 1.1 * shaft_end],
            [0, 0],
            line_width=3,
            line_dash="dotdash",
            line_color=bokeh_colors[0],
        )

        # Bending Moment Diagram plot (BM)
        source_BM = ColumnDataSource(data=dict(x=nodes_pos, y=Bm))
        TOOLTIPS_BM = [("Bending Moment:", "@y")]
        BM = figure(
            tools=TOOLS,
            tooltips=TOOLTIPS_BM,
            width=800,
            height=400,
            title="Bending Moment Diagram",
            x_axis_label="Shaft lenght",
            y_axis_label="Bending Moment",
            x_range=[-0.1 * shaft_end, 1.1 * shaft_end],
        )
        i = 0
        while True:
            if i + 3 > len(nodes):
                break

            interpolated_BM = interpolate.interp1d(
                nodes_pos[i : i + 3], Bm[i : i + 3], kind="quadratic"
            )
            xnew_BM = np.linspace(
                nodes_pos[i], nodes_pos[i + 2], num=42, endpoint=True
            )

            ynew_BM = interpolated_BM(xnew_BM)
            auxsource_BM = ColumnDataSource(data=dict(x=xnew_BM, y=ynew_BM))
            BM.line(
                "x", "y", source=auxsource_BM, line_width=4, line_color=bokeh_colors[0]
            )
            i += 2
        BM.circle("x", "y", source=source_BM, size=8, fill_color=bokeh_colors[0])

        # BM - plot centerline
        BM.line(
            [-0.1 * shaft_end, 1.1 * shaft_end],
            [0, 0],
            line_width=3,
            line_dash="dotdash",
            line_color=bokeh_colors[0],
        )

        grid_plots = gridplot([[FBD, SF], [disp_graph, BM]])

        show(grid_plots)


class ConvergenceResults(Results):
    def plot(self, output_html=False):
        """This method plots:
            Natural Frequency vs Number of Elements
            Relative Error vs Number of Elements

        Parameters
        ----------
        output_html : Boolean, optional
            outputs a html file.
            Default is False

        Returns
        -------
        plot : bokeh.figure
            Bokeh plot showing the results
        --------
        """

        el_num = np.array(self[0])
        eigv_arr = np.array(self[1])
        error_arr = np.array(self[2])

        if output_html:
            output_file("convergence.html")

        source = ColumnDataSource(
            data=dict(x0=el_num, y0=eigv_arr, x1=el_num, y1=error_arr)
        )

        TOOLS = "pan,wheel_zoom,box_zoom,hover,reset,save,"
        TOOLTIPS1 = [("Frequency:", "@y0"), ("Number of Elements", "@x0")]
        TOOLTIPS2 = [("Relative Error:", "@y1"), ("Number of Elements", "@x1")]

        # create a new plot and add a renderer
        freq_arr = figure(
            tools=TOOLS,
            tooltips=TOOLTIPS1,
            width=800,
            height=600,
            title="Frequency Evaluation",
            x_axis_label="Numer of Elements",
            y_axis_label="Frequency (rad/s)",
        )
        freq_arr.line("x0", "y0", source=source, line_width=3, line_color="crimson")
        freq_arr.circle("x0", "y0", source=source, size=8, fill_color="crimson")

        # create another new plot and add a renderer
        rel_error = figure(
            tools=TOOLS,
            tooltips=TOOLTIPS2,
            width=800,
            height=600,
            title="Relative Error Evaluation",
            x_axis_label="Number of Elements",
            y_axis_label="Relative Error (%)",
        )
        rel_error.line(
            "x1", "y1", source=source, line_width=3, line_color="darkslategray"
        )
        rel_error.circle(
            "x1", "y1", source=source, fill_color="darkslategray", size=8
        )

        # put the subplots in a gridplot
        plot = gridplot([[freq_arr, rel_error]])
        # show the plots
        show(plot)

        return plot
